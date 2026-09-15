import json
from typing import AsyncGenerator

from pydantic_ai import RunContext
from pydantic_ai.result import StreamedRunResult

from app.assistant.agent import GroundedAnswer


async def stream_ai_sdk_compatible(
    run_result: StreamedRunResult[GroundedAnswer],
) -> AsyncGenerator[str, None]:
    """
    Consumes a Pydantic AI structured stream (GroundedAnswer).
    Yields standard Server-Sent Events (SSE) for the frontend:
      data: {"type": "text-delta", "text": "..."}\n\n
    """
    last_text = ""

    async for partial_answer in run_result.stream_output():
        if hasattr(partial_answer, "answer") and isinstance(partial_answer.answer, str):
            current_text = partial_answer.answer

            if current_text.startswith(last_text):
                delta = current_text[len(last_text):]
                if delta:
                    yield f"data: {json.dumps({'type': 'text-delta', 'text': delta})}\n\n"
                    last_text = current_text


