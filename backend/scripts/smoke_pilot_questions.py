"""Automated Smoke Test for 10 Client Brief Questions.

Tests hybrid retrieval, single-turn synthesis, and strict verbatim citation
grounding across the 10 core financial analyst evaluation questions.

Usage:
    # Run a single question (e.g. question #1):
    uv run python scripts/smoke_pilot_questions.py --question 1

    # Run all 10 questions sequentially (with rate-limit delays):
    uv run python scripts/smoke_pilot_questions.py --all
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.assistant.agent import DocumentAgentDeps, synthesis_agent
from app.database.session import SessionLocal
from app.grounding.validator import validate_grounding
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword_extraction import extract_keyword_terms, format_terms_for_fts
from app.retrieval.queries import full_text_search, semantic_search
from app.retrieval.retriever import embed_query

PILOT_QUESTIONS: dict[int, dict[str, str]] = {
    1: {
        "ticker": "AAPL",
        "question": "What was Apple's total net sales in fiscal 2024, and how did Services perform?",
    },
    2: {
        "ticker": "NVDA",
        "question": "What are NVIDIA's main risk factors regarding manufacturing and supply chain concentration?",
    },
    3: {
        "ticker": "MSFT",
        "question": "What was Microsoft's revenue growth in Intelligent Cloud and Server products?",
    },
    4: {
        "ticker": "AAPL",
        "question": "How much did Apple spend on Research and Development (R&D) in fiscal 2024 compared to 2023?",
    },
    5: {
        "ticker": "NVDA",
        "question": "What are the primary drivers of NVIDIA's Data Center revenue growth?",
    },
    6: {
        "ticker": "MSFT",
        "question": "What is Microsoft's capital expenditure outlook related to AI infrastructure?",
    },
    7: {
        "ticker": "AAPL",
        "question": "What were Apple's net sales by geographic segment (Americas, Europe, Greater China)?",
    },
    8: {
        "ticker": "NVDA",
        "question": "What legal proceedings or regulatory investigations are disclosed by NVIDIA?",
    },
    9: {
        "ticker": "MSFT",
        "question": "How does Microsoft describe its commercial remaining performance obligation (RPO)?",
    },
    10: {
        "ticker": "AAPL",
        "question": "What seasonal trends affect Apple's quarterly revenues?",
    },
}


async def test_question(q_num: int, ticker: str, question: str) -> dict:
    print("\n" + "=" * 80)
    print(f"[{q_num}/10] [{ticker}] {question}")
    print("=" * 80)

    db = SessionLocal()
    deps = DocumentAgentDeps(session=db)
    t0 = time.perf_counter()

    try:
        # 1. Retrieval
        kw_terms = extract_keyword_terms(question, use_llm=False)
        fts_query = format_terms_for_fts(kw_terms) if kw_terms else question
        query_emb = embed_query(question)

        semantic_res = semantic_search(db, query_emb, limit=8)
        fts_res = full_text_search(db, fts_query, limit=8)
        fused = reciprocal_rank_fusion(semantic_res, fts_res, k=60)

        top_chunks = [chunk for chunk, _ in fused[:4]]
        for c in top_chunks:
            deps.accessed_chunks[c.id] = c

        retrieval_ms = (time.perf_counter() - t0) * 1000
        print(f"  Retrieval: {len(top_chunks)} chunks found in {retrieval_ms:.0f}ms (Keywords: {', '.join(kw_terms[:4])})")

        # 2. Synthesis
        context_parts = []
        for c in top_chunks:
            doc = c.source_document
            src_label = f"{doc.ticker} {doc.filing_type} (FY{doc.filing_year})" if doc else "10-K"
            context_parts.append(
                f"### Source: {src_label} | Chunk ID: {c.id}\n{c.content}\n"
            )
        candidate_context = "\n---\n".join(context_parts)

        t_llm = time.perf_counter()
        raw_answer = None
        for attempt in range(4):
            try:
                res = await synthesis_agent.run(
                    f"User Question: {question}\n\nRetrieved 10-K Passages:\n{candidate_context}",
                    deps=deps,
                )
                raw_answer = res.data
                break
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str) and attempt < 3:
                    wait_sec = 3.0 * (attempt + 1)
                    print(f"  [LLM busy (503/429), waiting {wait_sec:.0f}s before retry {attempt + 1}/3...]")
                    await asyncio.sleep(wait_sec)
                else:
                    raise
        llm_ms = (time.perf_counter() - t_llm) * 1000

        # 3. Grounding Validation
        validated = validate_grounding(raw_answer, deps.accessed_chunks)
        total_ms = (time.perf_counter() - t0) * 1000

        print(f"  Synthesis: {llm_ms:.0f}ms | Total: {total_ms:.0f}ms")
        print("\n  Answer Preview:")
        for line in validated.answer.splitlines()[:4]:
            print(f"    {line}")
        if len(validated.answer.splitlines()) > 4:
            print("    ...")

        print(f"\n  Verified Citations: {len(validated.citations)}")
        for idx, cit in enumerate(validated.citations[:2], start=1):
            print(f"    [{idx}] \"{cit.quote[:90]}...\"")

        return {
            "q_num": q_num,
            "ticker": ticker,
            "status": "PASS",
            "chunks": len(top_chunks),
            "citations": len(validated.citations),
            "total_ms": total_ms,
            "error": None,
        }

    except Exception as e:
        total_ms = (time.perf_counter() - t0) * 1000
        print(f"  FAILED: {e}")
        return {
            "q_num": q_num,
            "ticker": ticker,
            "status": "FAIL",
            "chunks": 0,
            "citations": 0,
            "total_ms": total_ms,
            "error": str(e),
        }
    finally:
        db.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Pilot 10-Question Smoke Test")
    parser.add_argument("--question", type=int, default=None, help="Question number (1 to 10)")
    parser.add_argument("--all", action="store_true", help="Run all 10 questions")
    args = parser.parse_args()

    if args.question is not None:
        if args.question not in PILOT_QUESTIONS:
            print(f"Error: Question must be between 1 and 10. Given: {args.question}")
            sys.exit(1)
        selected = {args.question: PILOT_QUESTIONS[args.question]}
    elif args.all:
        selected = PILOT_QUESTIONS
    else:
        # Default to question 1
        selected = {1: PILOT_QUESTIONS[1]}

    results = []
    for num, item in selected.items():
        res = await test_question(num, item["ticker"], item["question"])
        results.append(res)
        # Avoid free tier RPM throttling between questions
        if len(selected) > 1 and num != list(selected.keys())[-1]:
            print("\n  [Sleeping 4s for free-tier rate limit friendliness...]")
            await asyncio.sleep(4.0)

    # Summary table
    print("\n" + "=" * 80)
    print("PILOT SMOKE TEST SUMMARY")
    print("=" * 80)
    print(f"{'#':<4} {'Ticker':<8} {'Status':<8} {'Chunks':<8} {'Citations':<12} {'Latency':<10}")
    print("-" * 55)
    for r in results:
        lat = f"{r['total_ms']:.0f}ms"
        print(f"{r['q_num']:<4} {r['ticker']:<8} {r['status']:<8} {r['chunks']:<8} {r['citations']:<12} {lat:<10}")

    passed = sum(1 for r in results if r["status"] == "PASS")
    print("-" * 55)
    print(f"Passed: {passed}/{len(results)} questions | 100% Free-Tier Architecture\n")


if __name__ == "__main__":
    asyncio.run(main())
