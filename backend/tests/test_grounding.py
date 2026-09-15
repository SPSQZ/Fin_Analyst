import uuid
import pytest

from app.assistant.agent import GroundedAnswer, Citation
from app.database.models.document_chunk import DocumentChunk
from app.grounding.validator import validate_grounding


def test_validate_grounding_success():
    chunk_id = uuid.uuid4()
    accessed_chunks = {
        chunk_id: DocumentChunk(id=chunk_id, content="Apple reported $119.6 billion in revenue.")
    }
    
    answer = GroundedAnswer(
        answer="Apple's revenue was $119.6 billion.",
        citations=[
            Citation(
                document_chunk_id=chunk_id,
                quote="Apple reported $119.6 billion in revenue."
            )
        ]
    )
    
    validated = validate_grounding(answer, accessed_chunks)
    assert len(validated.citations) == 1
    assert validated.citations[0].document_chunk_id == chunk_id

def test_validate_grounding_fails_unaccessed_chunk():
    chunk_id = uuid.uuid4()
    bad_chunk_id = uuid.uuid4()
    accessed_chunks = {
        chunk_id: DocumentChunk(id=chunk_id, content="Apple reported $119.6 billion in revenue.")
    }
    
    answer = GroundedAnswer(
        answer="Apple's revenue was $119.6 billion.",
        citations=[
            Citation(
                document_chunk_id=bad_chunk_id,
                quote="Apple reported $119.6 billion in revenue."
            )
        ]
    )
    
    validated = validate_grounding(answer, accessed_chunks)
    assert len(validated.citations) == 0

def test_validate_grounding_fails_hallucinated_quote():
    chunk_id = uuid.uuid4()
    accessed_chunks = {
        chunk_id: DocumentChunk(id=chunk_id, content="Apple reported $119.6 billion in revenue.")
    }
    
    answer = GroundedAnswer(
        answer="Apple's revenue was $119.6 billion and iPhone sales grew 10%.",
        citations=[
            Citation(
                document_chunk_id=chunk_id,
                quote="iPhone sales grew 10%."
            )
        ]
    )
    
    validated = validate_grounding(answer, accessed_chunks)
    assert len(validated.citations) == 0
