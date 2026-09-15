from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument
from data.ingest.chunking import PreparedChunk
from data.ingest.manifest import Filing, source_document_values


def get_or_create_source_document(
    db: Session, filing: Filing, markdown_content: str
) -> SourceDocument:
    document = db.scalar(
        select(SourceDocument).where(
            SourceDocument.accession_number == filing.accession_number
        )
    )
    values = source_document_values(filing, markdown_content)
    if document is None:
        document = SourceDocument(**values)
        db.add(document)
        db.flush()
    else:
        for field, value in values.items():
            setattr(document, field, value)
        db.flush()
    return document


def has_chunks(db: Session, source_document_id: uuid.UUID) -> bool:
    return db.scalar(
        select(DocumentChunk.id)
        .where(DocumentChunk.source_document_id == source_document_id)
        .limit(1)
    ) is not None


def write_chunks(
    db: Session,
    source_document: SourceDocument,
    chunks: list[PreparedChunk],
    vectors: list[list[float]],
    *,
    replace: bool = False,
) -> int:
    if len(chunks) != len(vectors):
        raise ValueError("Chunk and embedding counts do not match")
    if replace:
        db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.source_document_id == source_document.id
            )
        )
    for chunk, vector in zip(chunks, vectors, strict=True):
        db.add(
            DocumentChunk(
                source_document_id=source_document.id,
                chunk_index=chunk.index,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=vector,
                chunk_metadata=chunk.metadata,
            )
        )
    return len(chunks)