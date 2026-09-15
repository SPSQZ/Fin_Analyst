from data.ingest.chunking import build_chunker
from data.ingest.manifest import Filing


def test_chunker_uses_configured_token_limit():
    chunker = build_chunker(max_tokens=128)
    assert chunker.tokenizer.max_tokens == 128


def test_filing_metadata_contains_retrieval_filters():
    filing = Filing(
        ticker="AAPL",
        cik="0000320193",
        filing_type="10-K",
        filing_year=2025,
        filing_date="2025-10-31",
        report_date="2025-09-27",
        accession_number="0000320193-25-000079",
        source_url="https://example.com",
        markdown_path="2025/example.md",
    )
    metadata = filing.metadata()
    assert metadata["ticker"] == "AAPL"
    assert metadata["filing_year"] == 2025
    assert metadata["accession_number"] == "0000320193-25-000079"