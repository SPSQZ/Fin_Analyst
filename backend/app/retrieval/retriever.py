import functools
from collections import defaultdict
from dataclasses import dataclass

from google import genai
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database.models.document_chunk import DocumentChunk
from app.database.session import SessionLocal
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword_extraction import extract_keyword_terms, format_terms_for_fts
from app.retrieval.queries import full_text_search, semantic_search


class SearchFilters(BaseModel):
    ticker: str | None = None
    form: str | None = None
    year: int | None = None


@dataclass
class RetrievalDependencies:
    session: Session


_genai_client: genai.Client | None = None


def get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=settings.gemini_api_key)
    return _genai_client


@functools.lru_cache(maxsize=1024)
def _cached_embed_query(normalized_query: str) -> tuple[float, ...]:
    client = get_genai_client()
    res = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=[normalized_query],
        config={"output_dimensionality": settings.gemini_embedding_dimensions},
    )
    return tuple(res.embeddings[0].values)


def embed_query(query: str) -> list[float]:
    """Embed a search query using Gemini (with LRU caching to minimize API usage)."""
    normalized = query.strip().lower()
    return list(_cached_embed_query(normalized))


def fetch_neighbor_chunks(
    session: Session, fused_chunks: list[DocumentChunk], top_k: int = 5, window: int = 1
) -> list[DocumentChunk]:
    """
    Given a list of top retrieved chunks, fetch them along with their
    surrounding contextual neighbors (e.g. chunk_index - 1, chunk_index + 1).
    Returns the chunks ordered by document and chunk index so they read naturally.
    """
    top_chunks = fused_chunks[:top_k]

    needed_pairs = set()
    for c in top_chunks:
        for offset in range(-window, window + 1):
            target_idx = c.chunk_index + offset
            if target_idx >= 0:
                needed_pairs.add((c.source_document_id, target_idx))

    if not needed_pairs:
        return []

    doc_ids = list({doc_id for doc_id, _ in needed_pairs})

    stmt = (
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.source_document))
        .where(DocumentChunk.source_document_id.in_(doc_ids))
    )
    all_related = session.scalars(stmt).unique().all()

    final_chunks = [
        c
        for c in all_related
        if (c.source_document_id, c.chunk_index) in needed_pairs
    ]

    # Sort naturally by document and then chunk_index
    final_chunks.sort(key=lambda c: (str(c.source_document_id), c.chunk_index))
    return final_chunks


class DocumentRetriever:
    """Document retriever implementing hybrid vector + keyword search with optional filters."""

    def __init__(self, session: Session | None = None):
        self._session = session

    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        top_k: int = 5,
        window: int = 1,
        keyword_terms: list[str] | None = None,
    ) -> list[DocumentChunk]:
        session = self._session or SessionLocal()
        query_emb = embed_query(query)
        semantic_res = semantic_search(session, query_emb, limit=20, filters=filters)

        # Extract 3 to 5 high-impact keyword search terms for full-text search
        if keyword_terms is None:
            keyword_terms = extract_keyword_terms(query)

        fts_query = format_terms_for_fts(keyword_terms) if keyword_terms else query
        fts_res = full_text_search(session, fts_query, limit=20, filters=filters)

        fused = reciprocal_rank_fusion(semantic_res, fts_res)
        fused_chunks = [c for c, score in fused]
        return fetch_neighbor_chunks(
            session, fused_chunks, top_k=top_k, window=window
        )



def format_passages_for_agent(passages: list[DocumentChunk]) -> str:
    """Format retrieved passages for an agent or console inspection."""
    if not passages:
        return "No passages found."

    lines = []
    for c in passages:
        doc = c.source_document
        ticker = doc.ticker if doc else "UNKNOWN"
        form = doc.filing_type if doc else "10-K"
        year = f"FY{doc.filing_year}" if doc and doc.filing_year else ""
        meta = c.chunk_metadata or {}
        headings = meta.get("headings", [])
        section = f" ({headings[0]})" if headings else ""
        header = f"{ticker} {form} {year}{section} [{c.id}]:"
        lines.append(f"{header}\n{c.content}\n")
    return "\n".join(lines)


def retrieve_passages(
    session: Session,
    query: str,
    top_k: int = 5,
    window: int = 1,
    filters: SearchFilters | None = None,
    keyword_terms: list[str] | None = None,
) -> str:
    """
    End-to-end hybrid retrieval:
    1. Embed query (dense channel)
    2. Extract 3-5 keyword terms & format for FTS (sparse channel)
    3. Semantic search & FTS
    4. RRF fusion
    5. Contextual neighbors
    6. Formatting
    """
    retriever = DocumentRetriever(session=session)
    chunks = retriever.search(
        query=query,
        filters=filters,
        top_k=top_k,
        window=window,
        keyword_terms=keyword_terms,
    )
    return format_passages_for_agent(chunks)



import os
os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

# --- Pydantic AI Agent Setup ---

agent = Agent(
    "google:gemini-1.5-pro", # Note: can be configured via env later
    deps_type=RetrievalDependencies,
    system_prompt=(
        "You are an expert financial analyst. Use the provided `search_sec_filings` "
        "tool to search through ingested SEC filings to answer the user's questions. "
        "Always cite the source document (Ticker, Filing Type, Year) in your answers."
    ),
)


@agent.tool
def search_sec_filings(ctx: RunContext[RetrievalDependencies], query: str) -> str:
    """
    Search the SEC filings corpus for information relevant to the query.
    This performs a hybrid search (semantic + full text) and returns 
    relevant text chunks along with their surrounding context.
    """
    return retrieve_passages(ctx.deps.session, query, top_k=5, window=1)
