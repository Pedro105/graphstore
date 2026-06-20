"""Unit tests for the query classifier.

HeuristicClassifier is pure (no I/O), so its tests are plain assertions.
The threshold/LLM-fallback tests mock LLMClassifier so no real Anthropic
call happens.
"""

from unittest.mock import AsyncMock

import pytest

from contextstore.core.classifier import (
    CONFIDENCE_THRESHOLD,
    HeuristicClassifier,
    QueryClassifier,
    _LLMClassification,
)

heuristic = HeuristicClassifier()


# --- 3 examples per class: the obvious, high-confidence cases. ---


@pytest.mark.parametrize(
    "query",
    ["RG-88", "Recall R-2025-014", "Korrigan Cells Ltd", "LFP-9 Cell"],
)
def test_exact_lookup_examples(query):
    query_class, confidence = heuristic.classify(query)
    assert query_class == "exact_lookup"
    assert confidence >= CONFIDENCE_THRESHOLD


@pytest.mark.parametrize(
    "query",
    [
        "What does Vanta Battery Co manufacture?",
        "Who leads supply chain at Solstice Motors?",
        "What tools does Pedro use at ASML?",
    ],
)
def test_single_hop_examples(query):
    query_class, confidence = heuristic.classify(query)
    assert query_class == "single_hop"
    assert confidence >= CONFIDENCE_THRESHOLD


@pytest.mark.parametrize(
    "query",
    [
        "What is the root cause of the Solstice recall?",
        "Which institution influenced AuroraML's architecture?",
        "How is Dr. Chen connected to RG-88?",
    ],
)
def test_relational_examples(query):
    query_class, confidence = heuristic.classify(query)
    assert query_class == "relational"
    assert confidence >= CONFIDENCE_THRESHOLD


# --- Edge cases (the ones the task calls out explicitly). ---


def test_id_code_inside_a_relational_query_is_relational_not_exact_lookup():
    # Looks like an exact lookup (contains the code RG-88) but the bridging
    # phrase "connected to" must win -- relational language is checked first.
    query_class, confidence = heuristic.classify("How is RG-88 connected to Dr. Chen?")
    assert query_class == "relational"
    assert confidence >= CONFIDENCE_THRESHOLD


def test_how_many_is_single_hop_not_relational():
    # A "how" query that is actually a one-hop attribute question -- the
    # quantitative opener must suppress the generic "how" relational signal.
    query_class, confidence = heuristic.classify("How many cells does Vanta Battery Co produce?")
    assert query_class == "single_hop"
    assert confidence >= CONFIDENCE_THRESHOLD


def test_id_like_string_in_longer_relational_query_stays_relational():
    query_class, _ = heuristic.classify("What led to recall R-2025-014 at Solstice Motors?")
    assert query_class == "relational"


def test_bare_how_without_causal_phrase_is_low_confidence():
    # "how" leans relational but with no explicit causal/bridging phrase we
    # are not sure -- must fall below threshold so the LLM decides.
    query_class, confidence = heuristic.classify("How does the checkout service work?")
    assert query_class == "relational"
    assert confidence < CONFIDENCE_THRESHOLD


def test_keyword_bag_is_low_confidence():
    # The isolation-style keyword bag: no question word, no verb, no code,
    # not a proper-noun phrase -> low confidence -> LLM fallback.
    _, confidence = heuristic.classify(
        "biotech startup pancreatic cancer drug compound research pipeline"
    )
    assert confidence < CONFIDENCE_THRESHOLD


def test_long_id_code_query_is_below_threshold():
    # A code embedded in a longer non-question phrase is a weaker exact-lookup
    # signal (n > 4) and should defer to the LLM.
    query_class, confidence = heuristic.classify(
        "the RG-88 compound batch from the Helios pipeline last quarter"
    )
    assert query_class == "exact_lookup"
    assert confidence < CONFIDENCE_THRESHOLD


# --- Threshold / LLM fallback behaviour (LLMClassifier mocked). ---


async def test_high_confidence_does_not_call_the_llm():
    llm = AsyncMock()
    classifier = QueryClassifier(llm=llm)

    result = await classifier.classify("RG-88")

    assert result.query_class == "exact_lookup"
    assert result.used_llm is False
    assert result.strategy.retrieval_mode == "fulltext"
    assert result.strategy.traversal_depth == 1
    llm.classify.assert_not_awaited()


async def test_low_confidence_falls_back_to_the_llm():
    llm = AsyncMock()
    llm.classify.return_value = _LLMClassification(
        query_class="relational", reasoning="connects two clusters"
    )
    classifier = QueryClassifier(llm=llm)

    result = await classifier.classify(
        "biotech startup pancreatic cancer drug compound research pipeline"
    )

    llm.classify.assert_awaited_once()
    assert result.used_llm is True
    assert result.query_class == "relational"
    # LLM-decided class still maps through to a strategy.
    assert result.strategy.retrieval_mode == "hybrid"
    assert result.strategy.traversal_depth == 2


async def test_llm_result_class_drives_the_returned_strategy():
    llm = AsyncMock()
    llm.classify.return_value = _LLMClassification(
        query_class="exact_lookup", reasoning="it's just a product code"
    )
    classifier = QueryClassifier(llm=llm)

    result = await classifier.classify("How does the checkout service work?")

    assert result.used_llm is True
    assert result.query_class == "exact_lookup"
    assert result.strategy.retrieval_mode == "fulltext"
