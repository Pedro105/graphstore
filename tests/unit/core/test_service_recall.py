"""Unit tests for recall()'s limit semantics, fully mocked (no real API calls).

Regression coverage for Anomaly 4: `limit` must bound the vector-seed step
only. Traversal results from those seeds must survive even when `limit` is
tight enough that seeds alone would exceed it.
"""

from unittest.mock import AsyncMock

from contextstore.core.service import recall
from contextstore.graph.store import GraphStore
from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.vector.embeddings import EmbeddingProvider

SCOPE = Scope.from_dict({"tenant_id": "acme", "user_id": "u_1"})
PROVENANCE = Provenance(source="agent_1")
QUERY_EMBEDDING = [1.0, 0.0, 0.0, 0.0]


def make_entity(**overrides) -> Entity:
    defaults = dict(scope=SCOPE, provenance=PROVENANCE)
    defaults.update(overrides)
    return Entity(**defaults)


def make_mocks(
    seeds: list[tuple[Entity, float]],
    traversal_results: list[tuple[Entity, list[Relation]]],
    truncated: bool = False,
) -> tuple[GraphStore, EmbeddingProvider]:
    graph_store = AsyncMock(spec=GraphStore)
    graph_store.find_similar_entities.return_value = seeds
    graph_store.find_by_fulltext.return_value = []
    # recall() now drives multi-hop expansion through traverse_from_seeds,
    # which returns the seeds-plus-reached subgraph as
    # (entities, relations, truncated). Flatten the per-entity traversal
    # fixtures into that shape, including the seeds themselves.
    reached_entities = [entity for entity, _ in seeds]
    reached_relations: list[Relation] = []
    for entity, relations in traversal_results:
        reached_entities.append(entity)
        reached_relations.extend(relations)
    graph_store.traverse_from_seeds.return_value = (
        reached_entities,
        reached_relations,
        truncated,
    )
    embedding_provider = AsyncMock(spec=EmbeddingProvider)
    embedding_provider.embed.return_value = QUERY_EMBEDDING
    return graph_store, embedding_provider


async def test_traversal_neighbours_survive_a_tight_seed_limit():
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
        seeds=[(seed, 0.95)],
        traversal_results=[(neighbour, [relation])],
    )

    result = await recall(
        query="Acme Corp customer shipment",
        scope=SCOPE,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        limit=1,
        # Pin routing so this limit-semantics test skips the classifier
        # (caller-supplied params win) -- keeps it deterministic and offline.
        retrieval_mode="hybrid",
    )

    # Old (buggy) behaviour re-sliced the merged seeds+traversal set to
    # `limit`, which at limit=1 would silently drop the traversed neighbour
    # (and the relation to it) even though traversal found it correctly.
    entity_ids = {entity.id for entity in result.entities}
    assert entity_ids == {seed.id, neighbour.id}
    assert result.relations == [relation]


async def test_limit_bounds_the_vector_seed_step_not_the_final_result():
    seed = make_entity(name="Acme Corp", entity_type="Organization")
    graph_store, embedding_provider = make_mocks(seeds=[(seed, 0.95)], traversal_results=[])

    await recall(
        query="Acme Corp customer shipment",
        scope=SCOPE,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        limit=1,
        retrieval_mode="hybrid",
    )

    graph_store.find_similar_entities.assert_awaited_once()
    args = graph_store.find_similar_entities.await_args.args
    assert args[3] == 1
