import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models.document_chunk import DocumentChunk
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword_extraction import extract_keyword_terms, format_terms_for_fts
from app.retrieval.queries import full_text_search, semantic_search
from app.retrieval.retriever import embed_query

# Make sure API key is set for Pydantic AI
os.environ["GEMINI_API_KEY"] = settings.gemini_api_key

INSTRUCTIONS_PATH = Path(__file__).parent / "instructions.md"
with open(INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


@dataclass
class DocumentAgentDeps:
    session: Session
    # Track all chunks the agent sees during the run so we can validate citations
    accessed_chunks: dict[uuid.UUID, DocumentChunk] = field(default_factory=dict)
    # Optional callback to emit real-time pipeline status updates to the frontend
    status_emitter: Callable[[str], None] | None = None

    def emit_status(self, message: str) -> None:
        """Send a pipeline status update if a callback is wired."""
        if self.status_emitter is not None:
            self.status_emitter(message)


class Citation(BaseModel):
    document_chunk_id: uuid.UUID = Field(
        description="The exact UUID of the document chunk that supports the claim."
    )
    quote: str = Field(
        description="A verbatim quote from the text of the chunk that supports the claim. Must be an exact substring match."
    )


class GroundedAnswer(BaseModel):
    answer: str = Field(
        description="The comprehensive answer to the user's question, fully supported by the citations. Use standard markdown."
    )
    citations: list[Citation] = Field(
        description="List of citations supporting the answer. You MUST provide at least one citation if you answered the question factually."
    )


agent = Agent(
    f"google:{settings.gemini_chat_model}",
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    system_prompt=SYSTEM_PROMPT,
)

# Dedicated single-turn synthesis agent (guaranteeing exactly 1 LLM call)
synthesis_agent = Agent(
    f"google:{settings.gemini_chat_model}",
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    system_prompt=SYSTEM_PROMPT,
)

# High-availability fallback agent when Google servers spike with 503 UNAVAILABLE
synthesis_agent_fallback = Agent(
    "google:gemini-3.5-flash-lite",
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    system_prompt=SYSTEM_PROMPT,
)


@agent.tool
def search_filings(ctx: RunContext[DocumentAgentDeps], query: str) -> str:
    """
    Search the SEC filings corpus for information relevant to the query.
    Returns the top retrieved chunks, each labeled with its Chunk ID.
    You MUST record the Chunk ID if you use it in your answer.
    """
    # Stage 1: Extract keyword terms
    ctx.deps.emit_status("Extracting 3-5 financial search terms from your question...")
    keyword_terms = extract_keyword_terms(query)
    fts_query = format_terms_for_fts(keyword_terms) if keyword_terms else query
    terms_preview = ", ".join(keyword_terms[:5]) if keyword_terms else query[:60]

    # Stage 2: Dense vector search
    ctx.deps.emit_status(f"Searching SEC filings (semantic + keyword) for: {terms_preview}")
    query_emb = embed_query(query)
    semantic_res = semantic_search(ctx.deps.session, query_emb, limit=10)

    # Stage 3: Sparse full-text search
    fts_res = full_text_search(ctx.deps.session, fts_query, limit=10)

    # Stage 4: Reciprocal Rank Fusion
    ctx.deps.emit_status("Fusing vector & keyword results via Reciprocal Rank Fusion (RRF)...")
    fused = reciprocal_rank_fusion(semantic_res, fts_res, k=60)

    # Stage 5: Collect top chunks
    ctx.deps.emit_status(f"Found {len(fused)} candidate passages — selecting top 5...")
    output_parts = []
    for chunk, score in fused[:5]:  # Return top 5
        ctx.deps.accessed_chunks[chunk.id] = chunk
        doc = chunk.source_document
        output_parts.append(
            f"--- Chunk ID: {chunk.id} ---\n"
            f"Document: {doc.ticker} - {doc.filing_type} ({doc.filing_year})\n"
            f"Content:\n{chunk.content}\n"
        )

    ctx.deps.emit_status("Synthesizing analysis & citing source filing passages...")
    return "\n".join(output_parts) if output_parts else "No relevant filings found."


@agent.tool
def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: uuid.UUID) -> str:
    """
    Read the exact content of a specific chunk by its ID.
    """
    chunk = ctx.deps.session.get(DocumentChunk, chunk_id)
    if not chunk:
        return f"Chunk {chunk_id} not found."

    ctx.deps.accessed_chunks[chunk.id] = chunk
    doc = chunk.source_document
    return (
        f"--- Chunk ID: {chunk.id} ---\n"
        f"Document: {doc.ticker} - {doc.filing_type} ({doc.filing_year})\n"
        f"Content:\n{chunk.content}\n"
    )


@agent.tool
def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_id: uuid.UUID, window: int = 1
) -> str:
    """
    Read the chunks immediately before and after the given chunk_id to get more context.
    For example, window=1 returns the chunk before, the chunk itself, and the chunk after.
    """
    chunk = ctx.deps.session.get(DocumentChunk, chunk_id)
    if not chunk:
        return f"Chunk {chunk_id} not found."

    stmt = (
        select(DocumentChunk)
        .where(
            DocumentChunk.source_document_id == chunk.source_document_id,
            DocumentChunk.chunk_index >= chunk.chunk_index - window,
            DocumentChunk.chunk_index <= chunk.chunk_index + window,
        )
        .order_by(DocumentChunk.chunk_index)
    )

    surrounding = ctx.deps.session.scalars(stmt).all()

    output_parts = []
    for c in surrounding:
        ctx.deps.accessed_chunks[c.id] = c
        doc = c.source_document
        output_parts.append(
            f"--- Chunk ID: {c.id} ---\n"
            f"Document: {doc.ticker} - {doc.filing_type} ({doc.filing_year})\n"
            f"Content:\n{c.content}\n"
        )
    return "\n".join(output_parts)
