import uuid
import pytest

from app.database.models.document_chunk import DocumentChunk
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.retriever import retrieve_passages, embed_query
from app.database.session import SessionLocal

def test_reciprocal_rank_fusion():
    # Mock some chunks
    chunk1 = DocumentChunk(id=uuid.uuid4(), chunk_index=0)
    chunk2 = DocumentChunk(id=uuid.uuid4(), chunk_index=1)
    chunk3 = DocumentChunk(id=uuid.uuid4(), chunk_index=2)

    semantic_results = [chunk1, chunk2]
    fts_results = [chunk2, chunk3]

    # chunk1: sem=1, fts=0 -> score = 1/61
    # chunk2: sem=2, fts=1 -> score = 1/62 + 1/61
    # chunk3: sem=0, fts=2 -> score = 1/62

    # Expect order: chunk2 (highest), chunk1, chunk3
    fused = reciprocal_rank_fusion(semantic_results, fts_results, k=60)
    
    assert len(fused) == 3
    assert fused[0][0].id == chunk2.id
    assert fused[1][0].id == chunk1.id
    assert fused[2][0].id == chunk3.id
    
    assert fused[0][1] > fused[1][1]
    assert fused[1][1] > fused[2][1]

@pytest.mark.integration
def test_hybrid_search_integration():
    """
    Real query against ingested corpus in the database.
    Requires the DB to be populated with at least some chunks.
    """
    with SessionLocal() as session:
        # Check if DB has chunks
        if not session.query(DocumentChunk).first():
            pytest.skip("No chunks in database. Run ingestion first.")
            
        # Example query that should hit Apple or Microsoft documents
        query = "What was the total revenue?"
        
        # Test retrieve_passages which runs everything
        result_text = retrieve_passages(session, query, top_k=3, window=1)
        
        assert isinstance(result_text, str)
        assert len(result_text) > 0
        assert "Document:" in result_text
        assert "Chunk Index" in result_text
