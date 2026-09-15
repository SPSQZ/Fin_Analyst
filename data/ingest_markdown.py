# /// script
# requires-python = ">=3.12"
# ///
"""Load converted SEC Markdown filings into the source_documents table.

Run from the repository root with:

    uv run --directory backend python ..\\data\\ingest_markdown.py

The import is idempotent: an existing accession number is updated rather than
duplicated. This script stores source documents only; chunking and embeddings
are separate processing steps.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database.models.source_document import SourceDocument
from app.database.session import SessionLocal

DATA_DIR = Path(__file__).resolve().parent
MARKDOWN_DIR = DATA_DIR / "Markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
}


def parse_filing_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def ingest() -> tuple[int, int]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    created = 0
    updated = 0

    with SessionLocal.begin() as db:
        for entry in manifest["filings"]:
            markdown_path = entry.get("markdown_path")
            if not markdown_path:
                raise ValueError(
                    f"Manifest entry has no markdown_path: {entry['accession_number']}"
                )

            content_path = MARKDOWN_DIR / markdown_path
            content = content_path.read_text(encoding="utf-8")
            accession_number = entry["accession_number"]
            document = db.scalar(
                select(SourceDocument).where(
                    SourceDocument.accession_number == accession_number
                )
            )
            metadata = {
                "report_date": entry.get("report_date"),
                "primary_document": entry.get("primary_document"),
                "local_path": entry.get("local_path"),
                "markdown_path": markdown_path,
            }

            values = {
                "ticker": entry["ticker"],
                "company_name": COMPANY_NAMES.get(entry["ticker"], entry["ticker"]),
                "filing_type": entry["form"],
                "filing_year": int(entry["report_date"][:4]),
                "filing_date": parse_filing_date(entry.get("filing_date")),
                "accession_number": accession_number,
                "source_url": entry["source_url"],
                "markdown_content": content,
                "metadata_json": metadata,
            }
            if document is None:
                db.add(SourceDocument(**values))
                created += 1
            else:
                for field, value in values.items():
                    setattr(document, field, value)
                updated += 1

    return created, updated


if __name__ == "__main__":
    created_count, updated_count = ingest()
    print(f"Source documents created: {created_count}")
    print(f"Source documents updated: {updated_count}")