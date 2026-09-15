import logging
import uuid
from typing import Dict

from app.assistant.agent import GroundedAnswer, Citation
from app.database.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)

def validate_grounding(
    answer: GroundedAnswer, accessed_chunks: Dict[uuid.UUID, DocumentChunk]
) -> GroundedAnswer:
    """
    Validates that every citation in the GroundedAnswer maps strictly to an accessed chunk
    and that the quote is genuinely present in that chunk's text.
    
    If a citation fails, we drop it. In a stricter setting, we could raise an error to the LLM
    or fail the entire turn. Here, we'll strip invalid citations and log warnings.
    """
    valid_citations = []
    
    for citation in answer.citations:
        chunk_id = citation.document_chunk_id
        
        if chunk_id not in accessed_chunks:
            logger.warning(
                f"Grounding failure: Citation refers to unaccessed chunk ID {chunk_id}. Dropping citation."
            )
            continue
            
        chunk = accessed_chunks[chunk_id]
        
        # We enforce a loose verbatim check (ignore leading/trailing whitespace, maybe case-insensitive)
        # But we must ensure the quote is actually in the text to prevent hallucinations.
        cleaned_quote = citation.quote.strip()
        if cleaned_quote not in chunk.content:
            logger.warning(
                f"Grounding failure: Quote not found in chunk {chunk_id}. "
                f"Quote: '{cleaned_quote}'"
            )
            continue
            
        valid_citations.append(citation)
        
    return GroundedAnswer(answer=answer.answer, citations=valid_citations)
