# /// script
# requires-python = ">=3.12"
# dependencies = ["docling==2.124.0"]
# ///
"""Convert downloaded SEC HTML filings to Markdown with Docling.

Run from the repository root with:

    uv run data/convert_to_markdown.py

The output mirrors data/downloads/ under data/Markdown/ and writes a matching
manifest with a markdown_path added to each successfully converted filing.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter

DATA_DIR = Path(__file__).resolve().parent
SOURCE_DIR = DATA_DIR / "downloads"
OUTPUT_DIR = DATA_DIR / "Markdown"
SOURCE_MANIFEST = SOURCE_DIR / "manifest.json"
OUTPUT_MANIFEST = OUTPUT_DIR / "manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reconvert Markdown files that already exist.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Convert at most this many files, useful for a smoke test.",
    )
    return parser.parse_args()


def html_files() -> list[Path]:
    return sorted(
        path
        for path in SOURCE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in {".htm", ".html"}
    )


def output_path(source_path: Path) -> Path:
    return OUTPUT_DIR / source_path.relative_to(SOURCE_DIR).with_suffix(".md")


def load_manifest() -> dict[str, Any]:
    if not SOURCE_MANIFEST.exists():
        return {
            "source": "SEC EDGAR",
            "form": "10-K",
            "filings": [],
        }
    return json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))


def write_manifest(manifest: dict[str, Any], converted: int, failed: int) -> None:
    manifest["converted_at_utc"] = datetime.now(UTC).isoformat()
    manifest["converted_count"] = converted
    manifest["failed_count"] = failed
    OUTPUT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def convert_files(*, overwrite: bool, limit: int | None) -> int:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Source directory does not exist: {SOURCE_DIR}")

    sources = html_files()
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be at least 1")
        sources = sources[:limit]

    if not sources:
        raise FileNotFoundError(f"No HTML files found under {SOURCE_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    converter = DocumentConverter()
    manifest = load_manifest()
    manifest_by_path = {
        entry.get("local_path"): entry
        for entry in manifest.get("filings", [])
        if entry.get("local_path")
    }
    converted = 0
    failed = 0

    for index, source_path in enumerate(sources, start=1):
        relative_source = source_path.relative_to(SOURCE_DIR)
        destination = output_path(source_path)
        relative_output = destination.relative_to(OUTPUT_DIR).as_posix()
        entry = manifest_by_path.get(relative_source.as_posix()) or manifest_by_path.get(
            str(relative_source)
        )

        if destination.exists() and not overwrite:
            print(f"[{index}/{len(sources)}] skip {relative_output}")
            if entry is not None:
                entry["markdown_path"] = relative_output
                entry["conversion_status"] = "skipped_existing"
            converted += 1
            continue

        try:
            result = converter.convert(source_path)
            markdown = result.document.export_to_markdown()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(markdown, encoding="utf-8")
        except (OSError, RuntimeError, ValueError) as exc:
            failed += 1
            if entry is not None:
                entry["conversion_status"] = "failed"
                entry["conversion_error"] = str(exc)
            print(f"[{index}/{len(sources)}] FAILED {relative_source}: {exc}")
            continue

        converted += 1
        if entry is not None:
            entry["markdown_path"] = relative_output
            entry["conversion_status"] = "converted"
        print(f"[{index}/{len(sources)}] wrote {relative_output}")

    write_manifest(manifest, converted, failed)
    print(f"Converted: {converted}; failed: {failed}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Manifest: {OUTPUT_MANIFEST}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(convert_files(**vars(parse_args())))