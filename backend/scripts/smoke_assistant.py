import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ensure stdout uses utf-8 on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.assistant.agent import DocumentAgentDeps, agent
from app.database.session import SessionLocal
from app.grounding.validator import validate_grounding


async def run_query(query: str) -> None:
    print("\n" + "=" * 80)
    print(f"ANALYST QUERY: {query}")
    print("=" * 80)

    db = SessionLocal()
    deps = DocumentAgentDeps(session=db)

    try:
        print("\nRunning Assistant Agent (retrieving filings & generating grounded answer)...\n")

        async with agent.run_stream(query, deps=deps) as stream_result:
            final_answer = await stream_result.get_output()

        validated_answer = validate_grounding(final_answer, deps.accessed_chunks)

        print("-" * 80)
        print("GROUNDED ANSWER:")
        print("-" * 80)
        print(validated_answer.answer)
        print()

        print("-" * 80)
        print(f"VERIFIED CITATIONS ({len(validated_answer.citations)}):")
        print("-" * 80)

        if not validated_answer.citations:
            print("No citations returned.")
        else:
            for idx, citation in enumerate(validated_answer.citations, start=1):
                chunk = deps.accessed_chunks.get(citation.document_chunk_id)
                doc = chunk.source_document if chunk else None
                ticker = doc.ticker if doc else "UNKNOWN"
                filing_type = doc.filing_type if doc else "10-K"
                year = f"FY{doc.filing_year}" if doc and doc.filing_year else ""

                print(f"[{idx}] {ticker} {filing_type} {year} (Chunk ID: {citation.document_chunk_id})")
                print(f"    Verbatim Quote: \"{citation.quote}\"\n")

    except Exception as e:
        err_str = str(e)
        if any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "503", "quota"]):
            print("Google Gemini API rate limit reached (Free Tier: 5 req/min). Please wait ~15-20s and run again.")
        else:
            print(f"Error during assistant run: {e}")
    finally:
        db.close()


# ==============================================================================
# AVAILABLE PRE-SET QUERIES (1 through 5)
# ==============================================================================
AVAILABLE_QUERIES = {
    1: "What was Apple's total net sales in fiscal 2024 and how did iPhone perform?",
}


def main(
    # ==========================================================================
    # 🎯 QUERY CONTROLS (Run one query at a time):
    #
    # Option A: Pick a query number (1, 2, 3, 4, or 5):
    query_choice: int = 1,
    #
    # Option B: Or enter any custom question here (overrides query_choice if set):
    custom_query: str | None = None,
    # ==========================================================================
) -> None:
    """
    To run:
        uv run python scripts/smoke_assistant.py
    Change `query_choice` to 1, 2, 3, 4, or 5 to run a specific query.
    """
    if custom_query and custom_query.strip():
        selected_text = custom_query.strip()
        print(f"\n[Mode: Custom Query]")
    else:
        if query_choice not in AVAILABLE_QUERIES:
            print(f"\n❌ Invalid query_choice={query_choice}. Available choices are 1 to {len(AVAILABLE_QUERIES)}:")
            for num, q in AVAILABLE_QUERIES.items():
                print(f"   [{num}] {q}")
            return

        selected_text = AVAILABLE_QUERIES[query_choice]
        print(f"\n[Selected Query #{query_choice} of {len(AVAILABLE_QUERIES)}]")

    asyncio.run(run_query(selected_text))


if __name__ == "__main__":
    main()

