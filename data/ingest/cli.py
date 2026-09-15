from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.database.session import SessionLocal
from data.ingest.chunking import chunk_markdown
from data.ingest.config import MANIFEST_PATH, MARKDOWN_DIR
from data.ingest.database import get_or_create_source_document, has_chunks, write_chunks
from data.ingest.embeddings import create_embeddings
from data.ingest.manifest import load_filings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Maximum filings to process")
    parser.add_argument("--chunk-limit", type=int, default=None, help="Maximum chunks per filing")
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--write", action="store_true", help="Write source documents/chunks")
    parser.add_argument("--embed", action="store_true", help="Generate Gemini embeddings")
    parser.add_argument("--replace", action="store_true", help="Replace existing chunks")
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    if args.embed and not args.write:
        raise SystemExit("--embed requires --write")
    filings = load_filings(MANIFEST_PATH)
    if args.ticker:
        filings = [filing for filing in filings if filing.ticker == args.ticker.upper()]
    if args.year:
        filings = [filing for filing in filings if filing.filing_year == args.year]
    if args.limit is not None:
        filings = filings[: args.limit]
    if not filings:
        raise SystemExit("No filings matched the selected filters")

    for filing in filings:
        markdown_path = MARKDOWN_DIR / filing.markdown_path
        markdown_content = markdown_path.read_text(encoding="utf-8")
        chunks = chunk_markdown(markdown_path, filing, limit=args.chunk_limit)
        print(f"{filing.ticker} {filing.filing_year}: prepared {len(chunks)} chunk(s)")
        if not args.write:
            continue

        vectors = create_embeddings([chunk.content for chunk in chunks]) if args.embed else [[] for _ in chunks]
        if args.write and not args.embed:
            raise SystemExit("--write requires --embed for chunk rows with embeddings")

        with SessionLocal.begin() as db:
            source_document = get_or_create_source_document(
                db, filing, markdown_content
            )
            if has_chunks(db, source_document.id) and not args.replace:
                print("  skipped: chunks already exist")
                continue
            written = write_chunks(db, source_document, chunks, vectors, replace=args.replace)
            print(f"  wrote {written} chunk(s)")


if __name__ == "__main__":
    main(parse_args())