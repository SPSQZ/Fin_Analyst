from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import tiktoken
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

from data.ingest.config import CHUNK_MAX_TOKENS
from data.ingest.manifest import Filing


@dataclass(frozen=True)
class PreparedChunk:
    index: int
    content: str
    token_count: int
    metadata: dict


def build_chunker(max_tokens: int = CHUNK_MAX_TOKENS) -> HybridChunker:
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.encoding_for_model("text-embedding-3-small"),
        max_tokens=max_tokens,
    )
    return HybridChunker(
        tokenizer=tokenizer,
        repeat_table_header=True,
        merge_peers=True,
        omit_header_on_overflow=False,
        always_emit_headings=True,
    )


def chunk_markdown(
    markdown_path: Path,
    filing: Filing,
    *,
    chunker: HybridChunker | None = None,
    limit: int | None = None,
) -> list[PreparedChunk]:
    converter = DocumentConverter()
    document = converter.convert(markdown_path).document
    active_chunker = chunker or build_chunker()
    chunks: list[PreparedChunk] = []

    for index, chunk in enumerate(active_chunker.chunk(document)):
        content = active_chunker.contextualize(chunk).strip()
        if not content:
            continue
        chunk_metadata = chunk.meta.export_json_dict()
        headings = re.findall(r"^#{1,6}\s+(.+?)\s*$", content, flags=re.MULTILINE)
        metadata = {
            **filing.metadata(),
            "docling": chunk_metadata,
            "page_numbers": chunk_metadata.get("page_numbers", []),
            "headings": headings or chunk_metadata.get("headings", []),
            "section": headings[-1] if headings else None,
        }
        token_count = active_chunker.tokenizer.count_tokens(content)
        chunks.append(
            PreparedChunk(
                index=index,
                content=content,
                token_count=token_count,
                metadata=metadata,
            )
        )
        if limit is not None and len(chunks) >= limit:
            break

    return chunks