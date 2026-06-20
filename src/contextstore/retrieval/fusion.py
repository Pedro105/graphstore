"""Reciprocal Rank Fusion: merge ranked candidate lists from independent
retrieval methods (vector similarity, full-text keyword search) into one
ranked list, without needing the methods' scores to be on comparable scales.

Pure Python, no graph/store dependency -- the seed step in
`core/service.py` is the only caller.
"""

from uuid import UUID

DEFAULT_K_RRF = 60


def reciprocal_rank_fusion(
    vector_results: list[tuple[UUID, int]],
    fulltext_results: list[tuple[UUID, int]],
    k_rrf: int = DEFAULT_K_RRF,
) -> list[tuple[UUID, float]]:
    """Fuse two (entity_id, rank) lists into one (entity_id, score) list.

    `rank` is 1-based, best match first, independently per input list. An
    entity's fused score is the sum of `1 / (rank + k_rrf)` over every list
    it appears in -- entities appearing in both lists score higher than
    entities appearing in only one, without either list's raw scores ever
    being compared directly. Returned sorted by score descending.
    """
    scores: dict[UUID, float] = {}
    for entity_id, rank in vector_results:
        scores[entity_id] = scores.get(entity_id, 0.0) + 1.0 / (rank + k_rrf)
    for entity_id, rank in fulltext_results:
        scores[entity_id] = scores.get(entity_id, 0.0) + 1.0 / (rank + k_rrf)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
