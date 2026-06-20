"""Integration test for the classifier wired into the recall path, against a
real FalkorDB instance. Skips gracefully if FalkorDB isn't reachable.

No real LLM/embedding calls: a FakeEmbeddingProvider returns a fixed vector,
and the three queries are deliberately ones the heuristic classifies with
high confidence (used_llm must be False), so no Anthropic key is needed. The
assertions are on how each query was *routed* (classifier_result), which the
recall path now attaches to the response.
"""

import os
import uuid

import pytest
from falkordb.asyncio import FalkorDB

from contextstore.core.service import recall
from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.models.entity import Entity
from contextstore.models.memory import Memory
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope
from contextstore.vector.embeddings import EmbeddingProvider

QUERY_EMBEDDING = [1.0, 0.0, 0.0, 0.0]


class FakeEmbeddingProvider(EmbeddingProvider):
    async def embed(self, text: str) -> list[float]:
        return QUERY_EMBEDDING

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [QUERY_EMBEDDING for _ in texts]


def _falkordb_env() -> tuple[str, int]:
    return os.getenv("FALKORDB_HOST", "localhost"), int(os.getenv("FALKORDB_PORT", "6379"))


@pytest.fixture
async def store():
    host, port = _falkordb_env()
    probe = FalkorDB(host=host, port=port)
    try:
        await probe.connection.ping()
    except Exception as exc:
        pytest.skip(f"FalkorDB not reachable at {host}:{port}: {exc}")
    finally:
        await probe.connection.aclose()

    graph_store = FalkorDBGraphStore(host=host, port=port)
    yield graph_store
    await graph_store.aclose()


@pytest.fixture
async def scope(store):
    tid = f"classifytest{uuid.uuid4().hex[:16]}"
    s = Scope.from_dict({"tenant_id": tid, "user_id": "u_test"})
    await store.ensure_graph_initialized(tid, embedding_dimension=4)
    provenance = Provenance(source="integration_test")
    entity = Entity(
        name="RG-88",
        entity_type="component",
        scope=s,
        provenance=provenance,
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    await store.write_memory(
        Memory(content="seed", entities=[entity], scope=s, provenance=provenance)
    )
    yield s
    graph_name = f"tenant_{tid}"
    if graph_name in await store._client.list_graphs():
        await store._client.select_graph(graph_name).delete()


async def test_exact_lookup_query_is_routed_to_fulltext_depth1(store, scope):
    result = await recall(
        query="RG-88",
        scope=scope,
        graph_store=store,
        embedding_provider=FakeEmbeddingProvider(),
    )
    assert result.classifier_result is not None
    assert result.classifier_result.query_class == "exact_lookup"
    assert result.classifier_result.used_llm is False
    assert result.classifier_result.strategy.retrieval_mode == "fulltext"
    assert result.classifier_result.strategy.traversal_depth == 1


async def test_single_hop_query_is_routed_to_hybrid_depth1(store, scope):
    result = await recall(
        query="What does Vanta Battery Co manufacture?",
        scope=scope,
        graph_store=store,
        embedding_provider=FakeEmbeddingProvider(),
    )
    assert result.classifier_result is not None
    assert result.classifier_result.query_class == "single_hop"
    assert result.classifier_result.used_llm is False
    assert result.classifier_result.strategy.retrieval_mode == "hybrid"
    assert result.classifier_result.strategy.traversal_depth == 1


async def test_relational_query_is_routed_to_hybrid_depth2(store, scope):
    result = await recall(
        query="What is the root cause of the Solstice recall?",
        scope=scope,
        graph_store=store,
        embedding_provider=FakeEmbeddingProvider(),
    )
    assert result.classifier_result is not None
    assert result.classifier_result.query_class == "relational"
    assert result.classifier_result.used_llm is False
    assert result.classifier_result.strategy.retrieval_mode == "hybrid"
    assert result.classifier_result.strategy.traversal_depth == 2


async def test_caller_pinned_routing_skips_the_classifier(store, scope):
    result = await recall(
        query="RG-88",
        scope=scope,
        graph_store=store,
        embedding_provider=FakeEmbeddingProvider(),
        retrieval_mode="vector",
    )
    # Caller pinned retrieval_mode -> classifier skipped -> no result attached.
    assert result.classifier_result is None
