from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument


def semantic_search(
    session: Session, query_embedding: list[float], limit: int = 10, filters=None
) -> list[DocumentChunk]:
    """
    Perform semantic search using pgvector cosine distance.
    Optionally pre-filters by ticker, filing_type (form), or filing_year.
    Returns the top `limit` DocumentChunks.
    """
    stmt = select(DocumentChunk).options(joinedload(DocumentChunk.source_document))
    if filters and (
        getattr(filters, "ticker", None)
        or getattr(filters, "form", None)
        or getattr(filters, "year", None)
    ):
        stmt = stmt.join(DocumentChunk.source_document)
        if getattr(filters, "ticker", None):
            stmt = stmt.where(SourceDocument.ticker == filters.ticker)
        if getattr(filters, "form", None):
            stmt = stmt.where(SourceDocument.filing_type == filters.form)
        if getattr(filters, "year", None):
            stmt = stmt.where(SourceDocument.filing_year == filters.year)

    stmt = stmt.order_by(
        DocumentChunk.embedding.cosine_distance(query_embedding)
    ).limit(limit)
    return list(session.scalars(stmt).all())


def full_text_search(
    session: Session, query: str, limit: int = 10, filters=None
) -> list[DocumentChunk]:
    """
    Perform PostgreSQL full-text search against the content_search tsvector column.
    Uses websearch_to_tsquery to handle natural language queries gracefully.
    Optionally pre-filters by ticker, filing_type (form), or filing_year.
    Returns the top `limit` DocumentChunks ordered by ts_rank.
    """
    tsquery = func.websearch_to_tsquery("english", query)
    stmt = (
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.source_document))
        .where(DocumentChunk.content_search.op("@@")(tsquery))
    )

    if filters and (
        getattr(filters, "ticker", None)
        or getattr(filters, "form", None)
        or getattr(filters, "year", None)
    ):
        stmt = stmt.join(DocumentChunk.source_document)
        if getattr(filters, "ticker", None):
            stmt = stmt.where(SourceDocument.ticker == filters.ticker)
        if getattr(filters, "form", None):
            stmt = stmt.where(SourceDocument.filing_type == filters.form)
        if getattr(filters, "year", None):
            stmt = stmt.where(SourceDocument.filing_year == filters.year)

    stmt = stmt.order_by(
        func.ts_rank(DocumentChunk.content_search, tsquery).desc()
    ).limit(limit)
    return list(session.scalars(stmt).all())


