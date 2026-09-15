import asyncio
import json
import uuid
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from app.assistant.agent import synthesis_agent, synthesis_agent_fallback, DocumentAgentDeps
from app.chat.streaming import stream_ai_sdk_compatible
from app.database.models.chat_message import ChatMessage
from app.database.models.message_citation import MessageCitation
from app.grounding.validator import validate_grounding
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.keyword_extraction import extract_keyword_terms, format_terms_for_fts
from app.retrieval.queries import full_text_search, semantic_search
from app.retrieval.retriever import embed_query


async def process_chat_turn(
    session: Session, thread_id: uuid.UUID, user_text: str
) -> AsyncGenerator[str, None]:
    """
    Orchestrates a single turn of chat with maximum quota efficiency:
    1. Saves user message.
    2. Runs hybrid search directly in Python (0 LLM calls for keywords, cached embeddings).
    3. Feeds pre-retrieved passages into synthesis_agent (exactly 1 LLM call).
    4. Validates citations against accessed chunks.
    5. Saves assistant message & citations and yields enriched payload.
    """
    # 1. Save user message
    from sqlalchemy import func
    max_seq = session.query(func.max(ChatMessage.sequence)).filter(ChatMessage.thread_id == thread_id).scalar()
    next_seq = (max_seq or 0) + 1

    user_msg = ChatMessage(thread_id=thread_id, role="user", sequence=next_seq, content=user_text)
    session.add(user_msg)
    session.commit()

    deps = DocumentAgentDeps(session=session)

    try:
        # Step 1: Extract keywords using heuristic (0 API calls)
        yield f"data: {json.dumps({'type': 'status', 'message': 'Extracting financial search terms...'})}\n\n"
        keyword_terms = extract_keyword_terms(user_text, use_llm=False)
        fts_query = format_terms_for_fts(keyword_terms) if keyword_terms else user_text
        terms_preview = ", ".join(keyword_terms[:4]) if keyword_terms else user_text[:50]

        # Step 2: Dense & sparse search with cached embeddings (1 or 0 API calls)
        yield f"data: {json.dumps({'type': 'status', 'message': f'Searching SEC filings for: {terms_preview}'})}\n\n"
        query_emb = embed_query(user_text)
        semantic_res = semantic_search(session, query_emb, limit=8)
        fts_res = full_text_search(session, fts_query, limit=8)

        # Step 3: Reciprocal Rank Fusion
        yield f"data: {json.dumps({'type': 'status', 'message': 'Fusing vector & keyword results via RRF...'})}\n\n"
        fused = reciprocal_rank_fusion(semantic_res, fts_res, k=60)
        top_chunks = [chunk for chunk, _ in fused[:4]]  # Top 4 most relevant chunks
        for chunk in top_chunks:
            deps.accessed_chunks[chunk.id] = chunk

        # Step 4: Build direct context prompt for single-turn synthesis
        if top_chunks:
            formatted_passages = []
            for c in top_chunks:
                doc = c.source_document
                formatted_passages.append(
                    f"--- Chunk ID: {c.id} ---\n"
                    f"Document: {doc.ticker} - {doc.filing_type} ({doc.filing_year})\n"
                    f"Content:\n{c.content}"
                )
            context_str = "\n\n".join(formatted_passages)
            synthesis_prompt = (
                f"User Question: {user_text}\n\n"
                f"Relevant SEC Filing Passages:\n{context_str}\n\n"
                "Instructions: Synthesize a clear, comprehensive, and objective answer to the user's question using ONLY the provided filing passages. "
                "Every factual claim or metric MUST be cited with the exact document_chunk_id and verbatim quote."
            )
        else:
            synthesis_prompt = (
                f"User Question: {user_text}\n\n"
                "No matching SEC filing passages were found for this query in the current corpus. "
                "Politely state that there is not enough evidence in the provided filings to answer."
            )

        yield f"data: {json.dumps({'type': 'status', 'message': 'Synthesizing analysis & citing source filing passages...'})}\n\n"

        final_answer = None
        for attempt in range(3):
            active_agent = synthesis_agent if attempt == 0 else synthesis_agent_fallback
            try:
                async with active_agent.run_stream(synthesis_prompt, deps=deps) as stream_result:
                    # Yield text-delta SSE chunks as the LLM streams the answer
                    async for chunk in stream_ai_sdk_compatible(stream_result):
                        yield chunk

                    # Get final structured output
                    final_answer = await stream_result.get_output()
                break
            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str) and attempt < 2:
                    wait_sec = 1.5 * (attempt + 1)
                    yield f"data: {json.dumps({'type': 'status', 'message': f'AI server busy, switching to high-availability pipeline ({wait_sec:.0f}s)...'})}\n\n"
                    await asyncio.sleep(wait_sec)
                else:
                    raise

        # Step 5: Validate citations against accessed chunks
        yield f"data: {json.dumps({'type': 'status', 'message': 'Validating citations against source chunks...'})}\n\n"
        validated_answer = validate_grounding(final_answer, deps.accessed_chunks)

        # Step 6: Save assistant message
        asst_msg = ChatMessage(thread_id=thread_id, role="assistant", sequence=next_seq + 1, content=validated_answer.answer)
        session.add(asst_msg)
        session.commit()  # commit to get asst_msg.id

        # Save citations & prepare payload
        citations_payload = []
        saved_chunk_ids: set[uuid.UUID] = set()

        for citation in validated_answer.citations:
            # Enforce uq_message_citations_message_chunk (one row per chunk per message in DB)
            if citation.document_chunk_id not in saved_chunk_ids:
                mc = MessageCitation(
                    message_id=asst_msg.id,
                    document_chunk_id=citation.document_chunk_id,
                    quote=citation.quote,
                    relevance_score=1.0,
                )
                session.add(mc)
                saved_chunk_ids.add(citation.document_chunk_id)

            chunk = deps.accessed_chunks.get(citation.document_chunk_id)
            doc = chunk.source_document if chunk else None
            citations_payload.append({
                "document_chunk_id": str(citation.document_chunk_id),
                "quote": citation.quote,
                "relevance_score": 1.0,
                "ticker": doc.ticker if doc else None,
                "company_name": doc.company_name if doc else None,
                "filing_type": doc.filing_type if doc else None,
                "filing_year": doc.filing_year if doc else None,
                "filing_date": doc.filing_date.isoformat() if doc and doc.filing_date else None,
                "accession_number": doc.accession_number if doc else None,
                "source_url": doc.source_url if doc else None,
                "chunk_index": chunk.chunk_index if chunk else None,
                "chunk_metadata": chunk.chunk_metadata if chunk else None,
                "content": chunk.content if chunk else None,
            })

        session.commit()

        # Send enriched citations to UI
        if citations_payload:
            yield f"data: {json.dumps({'type': 'citations', 'citations': citations_payload})}\n\n"

    except Exception as e:
        session.rollback()
        import traceback
        traceback.print_exc()
        print("ORCHESTRATOR ERROR CAUGHT:", repr(e))
        err_str = str(e)
        if any(term in err_str for term in ["503", "UNAVAILABLE"]):
            error_type = "provider_high_demand"
            error_msg = "Google Gemini servers are temporarily experiencing high global traffic. Please retry your question in a moment."
        elif any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "quota"]):
            error_type = "rate_limit_exceeded"
            error_msg = "Per-minute free tier request limit reached (15 RPM). Please wait 10 seconds before asking another question."
        elif "grounding" in err_str.lower():
            error_type = "grounding_failure"
            error_msg = "Grounding verification failed: The claims could not be verified against the source filing chunks."
        else:
            error_type = "assistant_error"
            error_msg = f"An error occurred while analyzing the filing: {err_str}"

        # Stream the error event and message to the UI
        yield f"data: {json.dumps({'type': 'error', 'error': error_msg, 'error_type': error_type})}\n\n"
        for word in error_msg.split(" "):
            yield f"data: {json.dumps({'type': 'text-delta', 'text': word + ' '})}\n\n"

        # Save error message to DB
        asst_msg = ChatMessage(thread_id=thread_id, role="assistant", sequence=next_seq + 1, content=error_msg)
        session.add(asst_msg)
        session.commit()

    yield "data: {\"type\": \"finish\"}\n\n"
