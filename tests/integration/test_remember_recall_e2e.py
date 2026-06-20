"""End-to-end test of the write/read core engine: real Claude (extraction),
real OpenAI (embeddings), real FalkorDB (graph + vector index).

Skips gracefully if FalkorDB isn't reachable, or if the real LLM/embedding
calls fail (e.g. ANTHROPIC_API_KEY / OPENAI_API_KEY missing or invalid) --
same "attempt and skip on failure" pattern as test_falkordb_connection.py.
"""

import os
import uuid

import pytest
from falkordb.asyncio import FalkorDB

from contextstore.core.config import get_settings
from contextstore.core.service import recall, remember
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
    tid = f"e2etest{uuid.uuid4().hex[:16]}"
    yield tid
    graph_name = f"tenant_{tid}"
    if graph_name in await graph_store._client.list_graphs():
        await graph_store._client.select_graph(graph_name).delete()


async def test_remember_then_recall_resolves_entities_across_facts(graph_store, tenant_id):
    settings = get_settings()
    embedding_provider = OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimension,
    )
    scope = Scope.from_dict({"tenant_id": tenant_id, "user_id": "u_test"})

    facts = [
        "Pedro Costa is the lead engineer on the ContextStore project.",
        "ContextStore is a GraphRAG-based memory layer for AI workflows.",
        "Pedro Costa previously worked at Acme Corp as a backend engineer.",
        "The ContextStore project depends on FalkorDB for graph storage.",
        "Pedro decided to use FalkorDB's native vector index instead of "
        "Postgres pgvector for entity embeddings in ContextStore.",
    ]

    written_memories = []
    try:
        for fact in facts:
            memory = await remember(
                content=fact,
                scope=scope,
                source="e2e_test",
                graph_store=graph_store,
                embedding_provider=embedding_provider,
            )
            written_memories.append(memory)
    except Exception as exc:
        pytest.skip(
            "Real LLM/embedding API call failed -- check ANTHROPIC_API_KEY and "
            f"OPENAI_API_KEY are set to real, valid keys: {exc}"
        )

    print("\n=== Entities/relations extracted per fact ===")
    for fact, memory in zip(facts, written_memories, strict=True):
        print(f"\nFact: {fact}")
        print(f"  Entities: {[(e.name, e.entity_type) for e in memory.entities]}")
        print(
            "  Relations: "
            f"{[(r.relation_type, r.source_entity_id, r.target_entity_id) for r in memory.relations]}"
        )

    result = await recall(
        query="What does Pedro Costa work on?",
        scope=scope,
        graph_store=graph_store,
        embedding_provider=embedding_provider,
        limit=10,
        traversal_depth=1,
    )

    print("\n=== Recall result ===")
    print(f"Entities: {[(e.name, e.entity_type) for e in result.entities]}")
    print(
        "Relations: "
        f"{[(r.relation_type, r.source_entity_id, r.target_entity_id) for r in result.relations]}"
    )

    entity_names = {e.name.lower() for e in result.entities}
    assert any("pedro" in name for name in entity_names)
    assert any("contextstore" in name for name in entity_names)

    # Pedro Costa was extracted from 3 separate facts -- resolution should
    # have converged these mentions onto few distinct entities, not 3.
    all_written_entities = [e for m in written_memories for e in m.entities]
    pedro_mentions = [e for e in all_written_entities if "pedro" in e.name.lower()]
    distinct_pedro_ids = {e.id for e in pedro_mentions}
    print(
        f"\nPedro mentions: {len(pedro_mentions)}, distinct resolved ids: {len(distinct_pedro_ids)}"
    )
    assert len(distinct_pedro_ids) < len(pedro_mentions)
