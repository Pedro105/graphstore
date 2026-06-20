"""Unit tests for entity resolution thresholds, fully mocked (no real API calls)."""

from unittest.mock import AsyncMock

import pytest

from contextstore.extraction.schemas import ExtractedEntity
from contextstore.graph.store import GraphStore
from contextstore.models.claim import apply_claim, derive_active_view
from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope
from contextstore.resolution.entity_resolver import resolve_entity
from contextstore.vector.embeddings import EmbeddingProvider

SCOPE = Scope.from_dict({"tenant_id": "acme", "user_id": "u_1"})
PROVENANCE = Provenance(source="agent_1")
EXTRACTED = ExtractedEntity(name="Pedro Costa", entity_type="person")
QUERY_EMBEDDING = [1.0, 0.0, 0.0, 0.0]


def make_existing_entity(**overrides) -> Entity:
    defaults = dict(
        name="Pedro",
        entity_type="person",
        scope=SCOPE,
        provenance=PROVENANCE,
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    defaults.update(overrides)
    return Entity(**defaults)


def make_mocks(candidates: list[tuple[Entity, float]]) -> tuple[GraphStore, EmbeddingProvider]:
    graph_store = AsyncMock(spec=GraphStore)
    graph_store.find_similar_entities.return_value = candidates
    embedding_provider = AsyncMock(spec=EmbeddingProvider)
    embedding_provider.embed.return_value = QUERY_EMBEDDING
    return graph_store, embedding_provider


async def test_no_candidates_creates_new_entity():
    graph_store, embedding_provider = make_mocks([])

    result = await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    assert result.name == "Pedro Costa"
    assert result.entity_type == "person"
    assert result.merge_candidates == []
    assert result.embedding == QUERY_EMBEDDING
    assert result.scope == SCOPE
    assert result.provenance == PROVENANCE


async def test_below_candidate_threshold_creates_new_entity_with_no_merge_candidates():
    existing = make_existing_entity()
    graph_store, embedding_provider = make_mocks([(existing, 0.5)])

    result = await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    assert result.id != existing.id
    assert result.merge_candidates == []


async def test_candidate_threshold_range_records_merge_candidate():
    existing = make_existing_entity()
    graph_store, embedding_provider = make_mocks([(existing, 0.85)])

    result = await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    assert result.id != existing.id
    assert result.merge_candidates == [existing.id]


async def test_at_or_above_merge_threshold_merges_into_existing_entity():
    existing = make_existing_entity()
    graph_store, embedding_provider = make_mocks([(existing, 0.95)])

    result = await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    # Identity is preserved, but the merge is no longer a silent no-op: the
    # new write's touch is recorded as a claim, not discarded.
    assert result.id == existing.id
    assert result.name == existing.name
    assert result.embedding == existing.embedding
    assert len(result.claims) == len(existing.claims) + 1
    assert result.contributing_sources == ["agent_1"]


async def test_merge_records_conflicting_property_and_supersedes_prior_claim():
    prior_claims = apply_claim([], Provenance(source="agent_1"), {"price": "4.20"})
    prior_properties, prior_provenance, prior_sources = derive_active_view(prior_claims)
    existing = make_existing_entity(
        properties=prior_properties,
        provenance=prior_provenance,
        claims=prior_claims,
        contributing_sources=prior_sources,
    )
    graph_store, embedding_provider = make_mocks([(existing, 0.95)])
    extracted = ExtractedEntity(
        name="Pedro Costa", entity_type="person", properties={"price": "4.50"}
    )

    result = await resolve_entity(extracted, SCOPE, PROVENANCE, graph_store, embedding_provider)

    assert result.properties == {"price": "4.50"}
    price_claims = [c for c in result.claims if c.property_name == "price"]
    assert len(price_claims) == 2
    old_claim, new_claim = price_claims
    assert old_claim.value == "4.20"
    assert new_claim.value == "4.50"
    assert new_claim.provenance.supersedes == [str(old_claim.id)]


async def test_merge_with_no_new_properties_still_records_a_touch_claim():
    existing = make_existing_entity()
    assert existing.claims == []
    graph_store, embedding_provider = make_mocks([(existing, 0.95)])

    result = await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    assert len(result.claims) == 1
    assert result.claims[0].property_name is None
    assert result.contributing_sources == ["agent_1"]


@pytest.mark.parametrize(
    "score,expect_reuse",
    [
        (0.92, True),
        (0.9199, "candidate"),
        (0.80, "candidate"),
        (0.7999, False),
    ],
)
async def test_threshold_boundaries(score, expect_reuse):
    existing = make_existing_entity()
    graph_store, embedding_provider = make_mocks([(existing, score)])

    result = await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    if expect_reuse is True:
        assert result.id == existing.id
    elif expect_reuse == "candidate":
        assert result.id != existing.id
        assert result.merge_candidates == [existing.id]
    else:
        assert result.id != existing.id
        assert result.merge_candidates == []


async def test_embeds_entity_type_and_name():
    graph_store, embedding_provider = make_mocks([])

    await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    embedding_provider.embed.assert_awaited_once_with("person: Pedro Costa")


async def test_searches_within_scope_filtered_by_entity_type():
    graph_store, embedding_provider = make_mocks([])

    await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    graph_store.find_similar_entities.assert_awaited_once()
    args = graph_store.find_similar_entities.await_args.args
    assert args[0] == SCOPE
    assert args[1] == QUERY_EMBEDDING
    assert args[2] == "person"


async def test_only_top_candidate_decides_outcome_even_with_multiple_results():
    best = make_existing_entity(name="Best")
    second = make_existing_entity(name="Second")
    graph_store, embedding_provider = make_mocks([(best, 0.95), (second, 0.99)])

    result = await resolve_entity(EXTRACTED, SCOPE, PROVENANCE, graph_store, embedding_provider)

    # First candidate in the list wins regardless of relative score ordering --
    # find_similar_entities is responsible for returning best-first.
    assert result.id == best.id
    assert result.name == best.name
