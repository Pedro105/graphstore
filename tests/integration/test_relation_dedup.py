"""Regression test for a duplicate-edge bug found via manual dogfooding:
writing the same relation between the same two (already-resolved) entities
via two separate remember() calls produced two edges instead of one.

Relations are now deduplicated at write time via MERGE keyed on
(source_entity_id, target_entity_id, relation_type) -- see
graph/falkordb_store.py's module docstring. This test encodes the exact
scenario: two independently-phrased sentences that each state the same
fact about the same two entities.

Uses real Claude (extraction) + real OpenAI (embeddings) + real FalkorDB,
same "attempt and skip on failure" pattern as the other E2E tests.
"""

import os
import uuid

import pytest
from falkordb.asyncio import FalkorDB

from contextstore.core.config import get_settings
from contextstore.core.service import remember
from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.models.scope import Scope
from contextstore.vector.embeddings import OpenAIEmbeddingProvider


def _falkordb_env() -> tuple[str, int]:
    return os.getenv("FALKORDB_HOST", "localhost"), int(os.getenv("FALKORDB_PORT", "6379"))


@pytest.fixture
async def graph_store():
    host, port = _falkordb_env()
    probe = FalkorDB(host=host, port=port)
    try:
        await probe.connection.ping()
    except Exception as exc:
        pytest.skip(f"FalkorDB not reachable at {host}:{port}: {exc}")
    finally:
        await probe.connection.aclose()

    store = FalkorDBGraphStore(host=host, port=port)
    yield store
    await store.aclose()


@pytest.fixture
async def tenant_id(graph_store):
    tid = f"dedup{uuid.uuid4().hex[:16]}"
    yield tid
    graph_name = f"tenant_{tid}"
    if graph_name in await graph_store._client.list_graphs():
        await graph_store._client.select_graph(graph_name).delete()


async def test_repeated_relation_between_same_entities_merges_not_duplicates(
    graph_store, tenant_id
):
    settings = get_settings()
    embedding_provider = OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimension,
    )
    scope = Scope.from_dict({"tenant_id": tenant_id, "user_id": "u_test"})

    sentence_1 = "Pedro works at ASML as a software engineer."
    sentence_2 = "Pedro has been working at ASML for the last two years."

    try:
        memory_1 = await remember(
            content=sentence_1,
            scope=scope,
            source="dedup_regression_test",
            graph_store=graph_store,
            embedding_provider=embedding_provider,
        )
        memory_2 = await remember(
            content=sentence_2,
            scope=scope,
            source="dedup_regression_test",
            graph_store=graph_store,
            embedding_provider=embedding_provider,
        )
    except Exception as exc:
        pytest.skip(
            "Real LLM/embedding API call failed -- check ANTHROPIC_API_KEY and "
            f"OPENAI_API_KEY are set to real, valid keys: {exc}"
        )

    pedro_ids = {
        e.id for m in (memory_1, memory_2) for e in m.entities if "pedro" in e.name.lower()
    }
    asml_ids = {e.id for m in (memory_1, memory_2) for e in m.entities if "asml" in e.name.lower()}

    print(f"\nPedro entity ids across both writes: {pedro_ids}")
    print(f"ASML entity ids across both writes: {asml_ids}")

    # Entity resolution should have converged each name onto a single entity
    # across both independent writes -- a precondition for this test to mean
    # anything (the bug being tested is about the relation edge, not entities).
    assert len(pedro_ids) == 1, f"expected Pedro to resolve to one entity, got {pedro_ids}"
    assert len(asml_ids) == 1, f"expected ASML to resolve to one entity, got {asml_ids}"

    pedro_id = next(iter(pedro_ids))
    asml_id = next(iter(asml_ids))

    graph = graph_store._graph_for(tenant_id)
    result = await graph.query(
        "MATCH (a:Entity {id: $pedro})-[r]->(b:Entity {id: $asml}) "
        "RETURN type(r), r.support_count, r.id",
        {"pedro": str(pedro_id), "asml": str(asml_id)},
    )

    print(f"Edges between Pedro and ASML: {result.result_set}")

    assert len(result.result_set) == 1, (
        f"expected exactly one edge between Pedro and ASML after two writes of the "
        f"same fact, found {len(result.result_set)}: {result.result_set}"
    )
    relation_type, support_count, _edge_id = result.result_set[0]
    print(f"Relation type: {relation_type!r}, support_count: {support_count}")
    assert support_count == 2
