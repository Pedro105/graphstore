"""Integration test for recall synthesis against the live eval_test graph.

Runs recall(synthesise=True) over an exact-lookup, a single-hop, and a
relational (2-hop) query and asserts each produces a non-empty, non-empty-data
prose answer. For the relational case, asserts at least one of the engineered
2-hop chain entities appears in grounded_entity_ids.

Skips gracefully if FalkorDB isn't reachable, eval_test hasn't been seeded, or
the real LLM/embedding calls fail (missing/invalid API keys) -- same pattern as
test_remember_recall_e2e.py and test_multihop_traversal.py.
"""

import os

import pytest
from falkordb.asyncio import FalkorDB

from contextstore.core.config import get_settings
from contextstore.core.service import recall
from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.models.scope import Scope
from contextstore.vector.embeddings import OpenAIEmbeddingProvider

TENANT_ID = "eval_test"


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
    if f"tenant_{TENANT_ID}" not in await store._client.list_graphs():
        await store.aclose()
        pytest.skip(f"tenant_{TENANT_ID} graph not seeded; run scripts/populate_graph.py")
    yield store
    await store.aclose()


@pytest.fixture
def embedding_provider():
    settings = get_settings()
    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimension,
    )


async def _recall(graph_store, embedding_provider, query, **kwargs):
    scope = Scope.from_dict({"tenant_id": TENANT_ID})
    try:
        return await recall(
            query=query,
            scope=scope,
            graph_store=graph_store,
            embedding_provider=embedding_provider,
            synthesise=True,
            **kwargs,
        )
    except Exception as exc:
        pytest.skip(f"Real LLM/embedding API call failed -- check API keys: {exc}")


# Per-case limit/depth mirror the eval-verified parameters in eval/dataset.yaml
# (exact_term_rg88, single_hop_korrigan_produces, bridging_korrigan_to_recall).
# On this small graph HNSW under-returns at larger k (Anomaly 3), so the
# seed-friendly limit differs per query -- the same reason the eval cases pin
# their own limit. retrieval_mode is left unset (defaults to hybrid, as the eval
# harness does by pinning only traversal_depth).


async def test_synthesis_exact_lookup(graph_store, embedding_provider):
    result = await _recall(graph_store, embedding_provider, "RG-88", limit=3, traversal_depth=1)
    assert result.synthesis is not None
    assert result.synthesis.answer.strip()
    assert result.synthesis.confidence != "insufficient_data"


async def test_synthesis_single_hop(graph_store, embedding_provider):
    result = await _recall(
        graph_store,
        embedding_provider,
        "What component does Korrigan Cells Ltd produce?",
        limit=2,
        traversal_depth=1,
    )
    assert result.synthesis is not None
    assert result.synthesis.answer.strip()
    assert result.synthesis.confidence != "insufficient_data"


async def test_synthesis_relational_grounds_in_chain(graph_store, embedding_provider):
    result = await _recall(
        graph_store,
        embedding_provider,
        "Korrigan Cells Ltd",
        limit=2,
        traversal_depth=2,
    )
    assert result.synthesis is not None
    assert result.synthesis.answer.strip()
    assert result.synthesis.confidence != "insufficient_data"

    # At least one entity from the engineered 2-hop chain (Korrigan -> ... ->
    # Voluntary Safety Recall R-2025-014) must be cited as grounding.
    chain_names = {"Korrigan Cells Ltd", "Voluntary Safety Recall R-2025-014"}
    chain_ids = {str(e.id) for e in result.entities if e.name in chain_names}
    assert chain_ids, "expected chain entities to be present in the retrieved subgraph"
    assert set(result.synthesis.grounded_entity_ids) & chain_ids, (
        "expected at least one 2-hop chain entity in grounded_entity_ids"
    )
