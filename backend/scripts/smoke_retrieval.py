import sys
from pathlib import Path

# Ensure backend root is in sys.path so app module is found
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure stdout uses utf-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.retrieval.keyword_extraction import extract_keyword_terms, format_terms_for_fts
from app.retrieval.retriever import (
    DocumentRetriever,
    SearchFilters,
    format_passages_for_agent,
)

# ==============================================================================
# AVAILABLE PRE-SET QUERIES & FILTERS (1 through 5)
# ==============================================================================
AVAILABLE_QUERIES = {
    1: (
        "What was Apple's total revenue and iPhone performance in 2022?",
        SearchFilters(ticker="AAPL", form="10-K", year=2022),
    ),
    2: (
        "How did NVIDIA describe demand drivers and customer concentration for its Data Center business?",
        SearchFilters(ticker="NVDA", form="10-K"),
    ),
    3: (
        "What changed in the way Microsoft describes Azure, AI infrastructure, and cloud capacity constraints?",
        SearchFilters(ticker="MSFT", form="10-K"),
    ),
    4: (
        "What was Amazon's AWS segment operating income and margin in fiscal 2024?",
        SearchFilters(ticker="AMZN", form="10-K", year=2024),
    ),
    5: (
        "What are Alphabet's primary advertising revenue streams and traffic acquisition costs?",
        SearchFilters(ticker="GOOGL", form="10-K"),
    ),
}


def main(
    # ==========================================================================
    # 🎯 QUERY CONTROLS (Run one query at a time):
    #
    # Option A: Pick a query number (1, 2, 3, 4, or 5):
    query_choice: int = 1,
    #
    # Option B: Or enter any custom question here:
    custom_query: str | None = None,
    top_k: int = 5,
    # ==========================================================================
) -> None:
    """
    To run:
        uv run python scripts/smoke_retrieval.py
    Change `query_choice` to 1, 2, 3, 4, or 5 to run a specific retrieval query.
    """
    if custom_query and custom_query.strip():
        query = custom_query.strip()
        filters = None
        print(f"\n[Mode: Custom Query]")
    else:
        if query_choice not in AVAILABLE_QUERIES:
            print(f"\n❌ Invalid query_choice={query_choice}. Available choices are 1 to {len(AVAILABLE_QUERIES)}:")
            for num, (q, _) in AVAILABLE_QUERIES.items():
                print(f"   [{num}] {q}")
            return

        query, filters = AVAILABLE_QUERIES[query_choice]
        print(f"\n[Selected Query #{query_choice} of {len(AVAILABLE_QUERIES)}]")

    print("\n" + "=" * 80)
    print(f"QUERY: {query}")
    if filters:
        print(f"FILTERS: {filters.model_dump_json()}")

    # Extract 3 to 5 keyword search terms for full-text search
    terms = extract_keyword_terms(query)
    fts_query = format_terms_for_fts(terms)
    print(f"EXTRACTED KEYWORD TERMS (3-5): {terms}")
    print(f"FORMATTED FTS QUERY: {fts_query}")
    print("=" * 80)

    retriever = DocumentRetriever()
    passages = retriever.search(query, filters=filters, top_k=top_k, keyword_terms=terms)
    print(format_passages_for_agent(passages))


if __name__ == "__main__":
    main()
