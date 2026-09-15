import json
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from supabase_auth.types import User as SupabaseUser

from app.auth.dependencies import get_current_user
from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.document_chunk import DocumentChunk
from app.database.models.message_citation import MessageCitation
from app.database.models.user import User
from app.database.session import get_db

router = APIRouter(prefix="/chat", tags=["chat"])
CurrentUser = Annotated[SupabaseUser, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]


class CreateThreadRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatMessageInput(BaseModel):
    role: str
    content: str | None = None
    parts: list[dict] | None = None


class StreamRequest(BaseModel):
    thread_id: uuid.UUID
    messages: list[ChatMessageInput] = Field(min_length=1)


def ensure_user(db: Session, current_user: SupabaseUser) -> User:
    user = db.get(User, uuid.UUID(current_user.id))
    if user is None:
        user = User(id=uuid.UUID(current_user.id), display_name=current_user.email)
        db.add(user)
        db.flush()
    return user


def get_owned_thread(db: Session, thread_id: uuid.UUID, user_id: uuid.UUID) -> ChatThread:
    thread = db.scalar(
        select(ChatThread).where(
            ChatThread.id == thread_id,
            ChatThread.user_id == user_id,
        )
    )
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this thread",
        )
    return thread


def serialize_citation(citation: MessageCitation) -> dict:
    chunk = citation.document_chunk
    doc = chunk.source_document if chunk else None
    return {
        "id": str(citation.id),
        "document_chunk_id": str(citation.document_chunk_id),
        "quote": citation.quote,
        "relevance_score": citation.relevance_score,
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
    }


def serialize_message(message: ChatMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "parts": message.parts,
        "sequence": message.sequence,
        "created_at": message.created_at.isoformat(),
        "citations": [serialize_citation(c) for c in (message.citations or [])],
    }


@router.get("/chunks/{chunk_id}")
def get_chunk_detail(
    chunk_id: uuid.UUID,
    current_user: CurrentUser,
    db: Database,
    window: int = 0,
) -> dict:
    chunk = db.get(DocumentChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Document chunk not found")

    doc = chunk.source_document
    result = {
        "id": str(chunk.id),
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "chunk_metadata": chunk.chunk_metadata,
        "ticker": doc.ticker if doc else None,
        "company_name": doc.company_name if doc else None,
        "filing_type": doc.filing_type if doc else None,
        "filing_year": doc.filing_year if doc else None,
        "filing_date": doc.filing_date.isoformat() if doc and doc.filing_date else None,
        "accession_number": doc.accession_number if doc else None,
        "source_url": doc.source_url if doc else None,
    }

    if window > 0:
        surrounding_stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.source_document_id == chunk.source_document_id,
                DocumentChunk.chunk_index >= chunk.chunk_index - window,
                DocumentChunk.chunk_index <= chunk.chunk_index + window,
            )
            .order_by(DocumentChunk.chunk_index)
        )
        surrounding = db.scalars(surrounding_stmt).all()
        result["surrounding"] = [
            {
                "id": str(c.id),
                "chunk_index": c.chunk_index,
                "content": c.content,
                "is_current": c.id == chunk.id,
            }
            for c in surrounding
        ]

    return result


@router.get("/threads")
def list_threads(current_user: CurrentUser, db: Database) -> list[dict]:
    user_id = uuid.UUID(current_user.id)
    threads = db.scalars(
        select(ChatThread)
        .where(ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
    ).all()
    return [
        {"id": str(thread.id), "title": thread.title, "updated_at": thread.updated_at.isoformat()}
        for thread in threads
    ]


@router.post("/threads", status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: CreateThreadRequest, current_user: CurrentUser, db: Database
) -> dict:
    user = ensure_user(db, current_user)
    thread = ChatThread(user_id=user.id, title=payload.title)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return {"id": str(thread.id), "title": thread.title, "updated_at": thread.updated_at.isoformat()}


@router.get("/threads/{thread_id}")
def get_thread(thread_id: uuid.UUID, current_user: CurrentUser, db: Database) -> dict:
    thread = get_owned_thread(db, thread_id, uuid.UUID(current_user.id))
    messages = sorted(thread.messages, key=lambda message: message.sequence)
    return {
        "id": str(thread.id),
        "title": thread.title,
        "messages": [serialize_message(message) for message in messages],
    }


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: uuid.UUID, current_user: CurrentUser, db: Database) -> None:
    thread = get_owned_thread(db, thread_id, uuid.UUID(current_user.id))
    db.delete(thread)
    db.commit()
    return None


def stream_stub_response(
    db: Session,
    thread: ChatThread,
    user_message: ChatMessageInput,
    assistant_sequence: int,
) -> Generator[str, None, None]:
    response_text = "I received your message. Retrieval will be connected in the next phase."
    for word in response_text.split(" "):
        yield f"data: {json.dumps({'type': 'text-delta', 'text': word + ' '})}\n\n"

    assistant_message = ChatMessage(
        thread_id=thread.id,
        role="assistant",
        sequence=assistant_sequence,
        content=response_text,
        parts=[{"type": "text", "text": response_text}],
    )
    db.add(assistant_message)
    thread.updated_at = datetime.now(UTC)
    db.commit()
    yield "data: {\"type\": \"finish\"}\n\n"


@router.post("/stream")
async def stream_chat(payload: StreamRequest, current_user: CurrentUser, db: Database):
    from app.chat.orchestrator import process_chat_turn
    
    thread = get_owned_thread(db, payload.thread_id, uuid.UUID(current_user.id))
    input_message = payload.messages[-1]
    if input_message.role != "user" or not (input_message.content or "").strip():
        raise HTTPException(status_code=422, detail="The last message must be a non-empty user message")

    # The orchestrator handles saving the user message and the assistant message
    return StreamingResponse(
        process_chat_turn(db, thread.id, input_message.content.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )