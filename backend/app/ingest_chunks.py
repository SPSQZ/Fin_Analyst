"""Ingestion script for parsing, chunking, embedding, and storing SEC filings.

Usage:
    uv run --directory backend python -m app.ingest_chunks --test-single-chunk
    uv run --directory backend python -m app.ingest_chunks
"""

import argparse
import logging
from pathlib import Path

from google import genai
from sqlalchemy import select
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.chunking import HierarchicalChunker

from app.database.models.source_document import SourceDocument
from app.database.models.document_chunk import DocumentChunk
from app.database.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Base directory for the data folder
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MARKDOWN_DIR = DATA_DIR / "Markdown"

BATCH_SIZE = 100  # Number of chunks to embed per API call


from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from google.genai.errors import APIError, ClientError

@retry(
    wait=wait_exponential(multiplier=2, min=15, max=120),
    stop=stop_after_attempt(7),
    retry=retry_if_exception_type((APIError, ClientError))
)
def embed_chunks(client: genai.Client, texts: list[str]) -> list[list[float]]:
    """Embed a list of text strings using Gemini text-embedding-004."""
    if not texts:
        return []
    
    # Pre-emptively wait a bit to avoid spiking RPM
    import time
    time.sleep(5)
    
    response = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=texts,
        config={"output_dimensionality": 768},
    )
    return [embedding.values for embedding in response.embeddings]


from app.config import settings

def ingest(test_single: bool = False):
    client = genai.Client(api_key=settings.gemini_api_key)
    converter = DocumentConverter(allowed_formats=[InputFormat.MD])
    chunker = HierarchicalChunker()

    with SessionLocal() as db:
        # Get documents that don't have chunks yet (Idempotent)
        subq = select(DocumentChunk.source_document_id).distinct()
        stmt = select(SourceDocument).where(SourceDocument.id.not_in(subq))
        
        if test_single:
            stmt = stmt.limit(1)

        documents = db.scalars(stmt).all()
        if not documents:
            logger.info("No new documents to ingest.")
            return

        for doc in documents:
            logger.info(f"Processing {doc.ticker} - {doc.filing_type} ({doc.filing_year})")
            md_path = doc.metadata_json.get("markdown_path")
            if not md_path:
                logger.warning(f"No markdown_path for {doc.accession_number}")
                continue

            full_md_path = MARKDOWN_DIR / md_path
            if not full_md_path.exists():
                logger.warning(f"File not found: {full_md_path}")
                continue

            # 1. Parse with Docling
            docling_result = converter.convert(str(full_md_path))
            
            # 2. Chunk
            docling_chunks = list(chunker.chunk(docling_result.document))
            
            if test_single:
                docling_chunks = docling_chunks[:1]
                logger.info("Test mode: Processing only 1 chunk.")

            # 3. Embed and Insert
            for i in range(0, len(docling_chunks), BATCH_SIZE):
                batch = docling_chunks[i : i + BATCH_SIZE]
                texts = [c.text for c in batch]
                
                # Extract rich metadata from Docling chunks
                metadatas = []
                for c in batch:
                    headings_attr = getattr(c.meta, 'headings', None)
                    headings = [h.text for h in headings_attr] if headings_attr else []
                    metadatas.append({
                        "ticker": doc.ticker,
                        "filing_year": doc.filing_year,
                        "filing_type": doc.filing_type,
                        "headings": headings
                    })

                embeddings = embed_chunks(client, texts)

                # Create DocumentChunk objects
                db_chunks = []
                for j, (text, embedding, metadata) in enumerate(zip(texts, embeddings, metadatas)):
                    db_chunk = DocumentChunk(
                        source_document_id=doc.id,
                        chunk_index=i + j,
                        content=text,
                        token_count=len(text) // 4,  # Rough estimate
                        embedding=embedding,
                        chunk_metadata=metadata,
                    )
                    db_chunks.append(db_chunk)
                
                db.add_all(db_chunks)
                db.commit()
                logger.info(f"Inserted {len(db_chunks)} chunks for {doc.accession_number}.")
                
                # Respect Gemini free tier rate limits (~15 RPM)
                import time
                time.sleep(4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest SEC filings into chunks.")
    parser.add_argument(
        "--test-single-chunk",
        action="store_true",
        help="Test mode: Process exactly one chunk from one document.",
    )
    args = parser.parse_args()

    ingest(test_single=args.test_single_chunk)
