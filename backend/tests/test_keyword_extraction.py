import pytest

from app.retrieval.keyword_extraction import (
    extract_keyword_terms,
    extract_terms_heuristic,
    format_terms_for_fts,
)


def test_heuristic_extraction_sample_queries():
    queries = [
        "What was Apple's total net sales in fiscal 2024 and how did iPhone perform?",
        "How did NVIDIA describe demand drivers and customer concentration for its Data Center business?",
        "What changed in the way Microsoft describes Azure, AI infrastructure, and cloud capacity constraints?",
        "What was Amazon's AWS segment operating income and margin in fiscal 2024?",
        "What are Alphabet's primary advertising revenue streams and traffic acquisition costs?",
    ]

    for q in queries:
        terms = extract_terms_heuristic(q, min_terms=3, max_terms=5)
        assert 3 <= len(terms) <= 5, f"Expected 3-5 terms for '{q}', got {terms}"
        # Stop words should not be included
        for t in terms:
            assert t.lower() not in {"what", "how", "did", "was", "and", "the", "in", "for"}


def test_format_terms_for_fts():
    terms = ["total net sales", "iPhone", "fiscal 2024"]
    formatted = format_terms_for_fts(terms)
    assert formatted == '"total net sales" OR iPhone OR "fiscal 2024"'

    empty_formatted = format_terms_for_fts([])
    assert empty_formatted == ""


def test_empty_query_handling():
    assert extract_keyword_terms("") == []
    assert extract_keyword_terms("   ") == []
    assert extract_terms_heuristic("") == []


def test_extract_keyword_terms_heuristic_fallback():
    query = "What was Apple's total net sales in fiscal 2024 and how did iPhone perform?"
    # When use_llm=False, it should use heuristic extractor
    terms = extract_keyword_terms(query, use_llm=False, min_terms=3, max_terms=5)
    assert 3 <= len(terms) <= 5
    assert any("net sales" in t.lower() for t in terms)


@pytest.mark.integration
def test_extract_keyword_terms_llm():
    query = "What was Amazon's AWS segment operating income and margin in fiscal 2024?"
    terms = extract_keyword_terms(query, use_llm=True, min_terms=3, max_terms=5)
    assert 3 <= len(terms) <= 5
    formatted = format_terms_for_fts(terms)
    assert "OR" in formatted
