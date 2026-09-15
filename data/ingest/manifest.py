from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Filing:
    ticker: str
    cik: str
    filing_type: str
    filing_year: int
    filing_date: str | None
    report_date: str | None
    accession_number: str
    source_url: str
    markdown_path: str

    @classmethod
    def from_entry(cls, entry: dict) -> Filing:
        return cls(
            ticker=entry["ticker"],
            cik=entry["cik"],
            filing_type=entry["form"],
            filing_year=int(entry["report_date"][:4]),
            filing_date=entry.get("filing_date"),
            report_date=entry.get("report_date"),
            accession_number=entry["accession_number"],
            source_url=entry["source_url"],
            markdown_path=entry["markdown_path"].replace("\\", "/"),
        )

    def metadata(self) -> dict:
        return {
            "ticker": self.ticker,
            "cik": self.cik,
            "filing_type": self.filing_type,
            "filing_year": self.filing_year,
            "filing_date": self.filing_date,
            "report_date": self.report_date,
            "accession_number": self.accession_number,
            "source_url": self.source_url,
            "markdown_path": self.markdown_path,
        }


def load_filings(manifest_path: Path) -> list[Filing]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [Filing.from_entry(entry) for entry in payload["filings"]]


def source_document_values(filing: Filing, markdown_content: str) -> dict:
    return {
        "ticker": filing.ticker,
        "company_name": filing.ticker,
        "filing_type": filing.filing_type,
        "filing_year": filing.filing_year,
        "filing_date": date.fromisoformat(filing.filing_date)
        if filing.filing_date
        else None,
        "accession_number": filing.accession_number,
        "source_url": filing.source_url,
        "markdown_content": markdown_content,
        "metadata_json": filing.metadata(),
    }