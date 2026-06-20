"""Integration test for multi-hop traverse_from_seeds against the live
eval_test graph (the 3 engineered 2-hop chains from scripts/populate_graph.py).

Each chain's end entity C must be ABSENT at depth=1 and PRESENT at depth=2 --
the same falsifiability the eval harness checks, exercised here directly
against the store. Skips gracefully if FalkorDB isn't reachable or eval_test
hasn't been seeded.
"""

import os

import pytest
from falkordb.asyncio import FalkorDB

from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.models.scope import Scope

TENANT_ID = "eval_test"

# (seed entity name, bridge-target entity name) for each engineered chain.
CHAINS = [
    ("Dr. Sarah Chen", "RG-88"),
    ("Dr. Amara Osei", "AuroraML"),
    ("Korrigan Cells Ltd", "Voluntary Safety Recall R-2025-014"),
]


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
    if f"tenant_{TENANT_ID}" not in await graph_store._client.list_graphs():
        await graph_store.aclose()
        pytest.skip(f"tenant_{TENANT_ID} graph not seeded; run scripts/populate_graph.py")
    yield graph_store
    await graph_store.aclose()


async def _seed_id(store: FalkorDBGraphStore, scope: Scope, name: str) -> str:
    entities = await store.find_entities(scope, name=name)
    if not entities:
        pytest.skip(f"seed entity {name!r} not found in {TENANT_ID}")
    return str(entities[0].id)


@pytest.mark.parametrize("seed_name,bridge_target", CHAINS)
async def test_bridge_target_absent_at_depth1_present_at_depth2(store, seed_name, bridge_target):
    scope = Scope.from_dict({"tenant_id": TENANT_ID})
    seed_id = await _seed_id(store, scope, seed_name)

    entities_d1, _, _ = await store.traverse_from_seeds(scope, [seed_id], depth=1)
    names_d1 = {entity.name for entity in entities_d1}
    assert seed_name in names_d1, f"seed {seed_name!r} should be in its own depth-1 subgraph"
    assert bridge_target not in names_d1, (
        f"{bridge_target!r} must NOT be reachable at depth=1 from {seed_name!r}"
    )

    entities_d2, _, _ = await store.traverse_from_seeds(scope, [seed_id], depth=2)
    names_d2 = {entity.name for entity in entities_d2}
    assert bridge_target in names_d2, (
        f"{bridge_target!r} must be reachable at depth=2 from {seed_name!r}"
    )


async def test_traverse_from_seeds_includes_seed_and_dedups(store):
    scope = Scope.from_dict({"tenant_id": TENANT_ID})
    seed_id = await _seed_id(store, scope, "Dr. Sarah Chen")

    entities, relations, truncated = await store.traverse_from_seeds(scope, [seed_id], depth=2)

    ids = [str(entity.id) for entity in entities]
    assert seed_id in ids
    assert len(ids) == len(set(ids)), "entities must be deduplicated"
    relation_ids = [str(relation.id) for relation in relations]
    assert len(relation_ids) == len(set(relation_ids)), "relations must be deduplicated"
    # Every returned relation has both endpoints inside the returned entity set.
    present = {str(entity.id) for entity in entities}
    for relation in relations:
        assert str(relation.source_entity_id) in present
        assert str(relation.target_entity_id) in present
    assert truncated is False


async def test_max_entities_cap_truncates_on_eval_graph(store):
    scope = Scope.from_dict({"tenant_id": TENANT_ID})
    seed_id = await _seed_id(store, scope, "Dr. Sarah Chen")

    # A tiny cap forces truncation on any non-trivial neighbourhood.
    entities, _, truncated = await store.traverse_from_seeds(
        scope, [seed_id], depth=2, max_entities=2
    )

    assert truncated is True
    assert len(entities) <= 2
