"""Integration test for the hybrid (vector + full-text RRF) recall path,
against a real FalkorDB instance. Skips gracefully if FalkorDB isn't
reachable -- same pattern as test_falkordb_store.py.

No real LLM/embedding API calls: entities are written directly via
write_memory() with hand-picked embeddings (like test_falkordb_store.py's
vector-ranking tests), and a FakeEmbeddingProvider returns a fixed query
embedding, so vector similarity is fully deterministic.

The scenario mirrors the problem statement: an alphanumeric identifier
("RG-88") whose embedding is deliberately unrelated to the query embedding
-- vector search alone has no way to find it, full-text search (an exact
substring/token match on the entity name) does.
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
    """Always returns the same fixed vector, regardless of input text --
    lets the test control vector similarity precisely without a real
    embedding API call."""

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
async def tenant_id(store):
    tid = f"hybridtest{uuid.uuid4().hex[:16]}"
    yield tid
    graph_name = f"tenant_{tid}"
    if graph_name in await store._client.list_graphs():
        await store._client.select_graph(graph_name).delete()


@pytest.fixture
async def seeded_scope(store, tenant_id):
    """Two decoys close to QUERY_EMBEDDING by cosine similarity (so vector
    search ranks them #1 and #2), and one exact-term entity ("RG-88")
    whose embedding is orthogonal to QUERY_EMBEDDING and whose name shares
    no tokens with the decoys -- vector search at limit=2 never sees it,
    full-text search on the query string "RG-88" only sees it.
    """
    scope = Scope.from_dict({"tenant_id": tenant_id, "user_id": "u_test"})
    await store.ensure_graph_initialized(tenant_id, embedding_dimension=4)
    provenance = Provenance(source="integration_test")

    decoy_close = Entity(
        name="Battery Module Alpha",
        entity_type="component",
        scope=scope,
        provenance=provenance,
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    decoy_far = Entity(
        name="Battery Module Beta",
        entity_type="component",
        scope=scope,
        provenance=provenance,
        embedding=[0.9, 0.1, 0.0, 0.0],
    )
    exact_term = Entity(
        name="RG-88",
        entity_type="component",
        scope=scope,
        provenance=provenance,
        embedding=[0.0, 1.0, 0.0, 0.0],
    )
    await store.write_memory(
        Memory(
            content="three components",
            entities=[decoy_close, decoy_far, exact_term],
            scope=scope,
            provenance=provenance,
        )
    )
    return scope


async def test_vector_only_misses_the_exact_term_entity(store, seeded_scope):
    result = await recall(
        query="RG-88",
        scope=seeded_scope,
        graph_store=store,
        embedding_provider=FakeEmbeddingProvider(),
        limit=2,
        retrieval_mode="vector",
    )

    names = {entity.name for entity in result.entities}
    assert names == {"Battery Module Alpha", "Battery Module Beta"}
    assert "RG-88" not in names


async def test_fulltext_only_finds_the_exact_term_entity(store, seeded_scope):
    result = await recall(
        query="RG-88",
        scope=seeded_scope,
        graph_store=store,
        embedding_provider=FakeEmbeddingProvider(),
        limit=2,
        retrieval_mode="fulltext",
    )

    names = {entity.name for entity in result.entities}
    assert names == {"RG-88"}


async def test_hybrid_recovers_the_exact_term_entity_vector_alone_misses(store, seeded_scope):
    result = await recall(
        query="RG-88",
        scope=seeded_scope,
        graph_store=store,
        embedding_provider=FakeEmbeddingProvider(),
        limit=2,
        retrieval_mode="hybrid",
    )

    names = {entity.name for entity in result.entities}
    assert "RG-88" in names
