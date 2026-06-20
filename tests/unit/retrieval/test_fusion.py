"""Unit tests for reciprocal_rank_fusion -- pure Python, no graph dependency."""

from uuid import uuid4

from contextstore.retrieval.fusion import reciprocal_rank_fusion

ENTITY_A = uuid4()
ENTITY_B = uuid4()
ENTITY_C = uuid4()


def test_identical_lists_double_the_score():
    ranked = [(ENTITY_A, 1), (ENTITY_B, 2)]

    fused = reciprocal_rank_fusion(ranked, ranked)

    scores = dict(fused)
    assert scores[ENTITY_A] == 2 * (1.0 / (1 + 60))
    assert scores[ENTITY_B] == 2 * (1.0 / (2 + 60))
    assert fused[0][0] == ENTITY_A  # rank-1 in both lists scores highest


def test_disjoint_lists_each_entity_keeps_its_single_list_score():
    vector_results = [(ENTITY_A, 1)]
    fulltext_results = [(ENTITY_B, 1)]

    fused = reciprocal_rank_fusion(vector_results, fulltext_results)

    scores = dict(fused)
    assert scores[ENTITY_A] == scores[ENTITY_B] == 1.0 / (1 + 60)
    assert {entity_id for entity_id, _ in fused} == {ENTITY_A, ENTITY_B}


def test_one_empty_list_falls_back_to_the_other():
    fused = reciprocal_rank_fusion([(ENTITY_A, 1), (ENTITY_B, 2)], [])

    assert fused == [
        (ENTITY_A, 1.0 / (1 + 60)),
        (ENTITY_B, 1.0 / (2 + 60)),
    ]


def test_both_empty_returns_empty():
    assert reciprocal_rank_fusion([], []) == []


def test_entity_in_only_one_list_ranks_below_an_entity_in_both():
    # C only in fulltext at rank 1; A in both vector(rank=2) and fulltext(rank=2).
    # A's fused score (two contributions) must beat C's (one contribution),
    # even though C's single-list rank is better than A's in that same list.
    vector_results = [(ENTITY_A, 2)]
    fulltext_results = [(ENTITY_C, 1), (ENTITY_A, 2)]

    fused = reciprocal_rank_fusion(vector_results, fulltext_results)

    scores = dict(fused)
    assert scores[ENTITY_A] == 2 * (1.0 / (2 + 60))
    assert scores[ENTITY_C] == 1.0 / (1 + 60)
    assert fused[0][0] == ENTITY_A


def test_custom_k_rrf_changes_the_score_but_not_the_formula():
    fused = reciprocal_rank_fusion([(ENTITY_A, 1)], [], k_rrf=1)

    assert fused == [(ENTITY_A, 1.0 / (1 + 1))]
