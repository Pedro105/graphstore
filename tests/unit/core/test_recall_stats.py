"""Unit tests for RetrievalStats on RecallResult, fully mocked (offline).

Asserts stats are present and well-formed across every recall path: synthesis
on/off, empty result, and a truncated subgraph; and that timing fields are
positive floats with synthesis_ms None exactly when synthesis didn't run.
"""

from unittest.mock import AsyncMock

from contextstore.core.service import recall
from contextstore.core.synthesiser import RecallSynthesiser
from contextstore.graph.store import GraphStore
from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.models.synthesis import SynthesisResult
from contextstore.vector.embeddings import EmbeddingProvider

SCOPE = Scope.from_dict({"tenant_id": "acme", "user_id": "u_1"})
PROVENANCE = Provenance(source="agent_1")


def make_entity(**overrides) -> Entity:
    defaults = dict(scope=SCOPE, provenance=PROVENANCE)
    defaults.update(overrides)
    return Entity(**defaults)


def make_mocks(
    seeds: list[tuple[Entity, float]],
    reached_entities: list[Entity],
    reached_relations: list[Relation],
    truncated: bool = False,
) -> tuple[GraphStore, EmbeddingProvider]:
    graph_store = AsyncMock(spec=GraphStore)
    graph_store.find_similar_entities.return_value = seeds
    graph_store.find_by_fulltext.return_value = []
    graph_store.traverse_from_seeds.return_value = (
        [entity for entity, _ in seeds] + reached_entities,
        reached_relations,
        truncated,
    )
    embedding_provider = AsyncMock(spec=EmbeddingProvider)
    embedding_provider.embed.return_value = [1.0, 0.0, 0.0, 0.0]
    return graph_store, embedding_provider


async def test_stats_present_without_synthesis():
    seed = make_entity(name="Acme Corp", entity_type="Organization")
    neighbour = make_entity(name="Product Y", entity_type="Product")
    relation = Relation(
        source_entity_id=seed.id,
        target_entity_id=neighbour.id,
        relation_type="depends_on",
        scope=SCOPE,
        provenance=PROVENANCE,
    )
    graph_store, embedding_provider = make_mocks(
        seeds=[(seed, 0.95)], reached_entities=[neighbour], reached_relations=[relation]
    )

    result = await recall(
        query="Acme Corp",
        scope=SCOPE,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        retrieval_mode="vector",
        traversal_depth=2,
    )

    stats = result.stats
    assert stats.seeds_found == 1
    assert stats.nodes_traversed == 2  # seed + neighbour
    assert stats.relations_found == 1
    assert stats.depth_reached == 2
    # Routing was pinned (retrieval_mode/traversal_depth given) -> no classifier.
    assert stats.query_class == "manual"
    assert stats.used_llm_classifier is False
    # Timing: positive floats, synthesis excluded (didn't run).
    assert isinstance(stats.total_ms, float) and stats.total_ms > 0.0
    assert isinstance(stats.retrieval_ms, float) and stats.retrieval_ms > 0.0
    assert stats.synthesis_ms is None
    assert stats.total_ms >= stats.retrieval_ms


async def test_stats_include_synthesis_ms_when_synthesis_runs():
    seed = make_entity(name="Acme Corp", entity_type="Organization")
    graph_store, embedding_provider = make_mocks(
        seeds=[(seed, 0.95)], reached_entities=[], reached_relations=[]
    )
    synthesiser = AsyncMock(spec=RecallSynthesiser)
    synthesiser.synthesise.return_value = SynthesisResult(
        answer="Acme Corp is an organization.",
        grounded_entity_ids=[str(seed.id)],
        confidence="high",
    )

    result = await recall(
        query="Acme Corp",
        scope=SCOPE,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        retrieval_mode="vector",
        traversal_depth=1,
        synthesise=True,
        synthesiser=synthesiser,
    )

    assert result.synthesis is not None
    assert result.stats.synthesis_ms is not None
    assert isinstance(result.stats.synthesis_ms, float)
    assert result.stats.synthesis_ms >= 0.0
    # total includes retrieval + synthesis.
    assert result.stats.total_ms >= result.stats.retrieval_ms


async def test_stats_present_on_empty_result():
    graph_store, embedding_provider = make_mocks(
        seeds=[], reached_entities=[], reached_relations=[]
    )

    result = await recall(
        query="nothing matches",
        scope=SCOPE,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        retrieval_mode="vector",
        traversal_depth=1,
    )

    assert result.entities == []
    assert result.stats.seeds_found == 0
    assert result.stats.nodes_traversed == 0
    assert result.stats.relations_found == 0
    assert result.stats.synthesis_ms is None
    assert result.stats.total_ms > 0.0


async def test_stats_present_on_truncated_result():
    seed = make_entity(name="Acme Corp", entity_type="Organization")
    neighbour = make_entity(name="Product Y", entity_type="Product")
    graph_store, embedding_provider = make_mocks(
        seeds=[(seed, 0.95)],
        reached_entities=[neighbour],
        reached_relations=[],
        truncated=True,
    )

    result = await recall(
        query="Acme Corp",
        scope=SCOPE,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        retrieval_mode="vector",
        traversal_depth=2,
        max_entities=2,
    )

    assert result.truncated is True
    assert result.stats.nodes_traversed == 2
    assert result.stats.depth_reached == 2
    assert result.stats.total_ms > 0.0
