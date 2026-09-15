from collections import defaultdict

from app.database.models.document_chunk import DocumentChunk


def reciprocal_rank_fusion(
    semantic_results: list[DocumentChunk],
    fts_results: list[DocumentChunk],
    k: int = 60,
) -> list[tuple[DocumentChunk, float]]:
    """
    Combine semantic search results and full-text search results using
    Reciprocal Rank Fusion (RRF).
    
    The RRF score for a chunk is the sum of (1 / (k + rank)) across both
    result sets. Higher scores are better.
    
    Returns:
        A list of tuples (DocumentChunk, rrf_score), sorted by score descending.
    """
    scores: dict[str, float] = defaultdict(float)
    chunks_by_id: dict[str, DocumentChunk] = {}

    for rank, chunk in enumerate(semantic_results, start=1):
        chunk_id_str = str(chunk.id)
        scores[chunk_id_str] += 1.0 / (k + rank)
        chunks_by_id[chunk_id_str] = chunk

    for rank, chunk in enumerate(fts_results, start=1):
        chunk_id_str = str(chunk.id)
        scores[chunk_id_str] += 1.0 / (k + rank)
        chunks_by_id[chunk_id_str] = chunk

    fused = [(chunks_by_id[chunk_id], score) for chunk_id, score in scores.items()]
    # Sort by descending RRF score
    fused.sort(key=lambda x: x[1], reverse=True)
    
    return fused
