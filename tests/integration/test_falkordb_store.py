"""Integration tests for FalkorDBGraphStore, run against a real FalkorDB instance.

Skips rather than fails if FalkorDB isn't reachable. Each test gets a fresh,
randomly-named tenant (and therefore a fresh FalkorDB graph), cleaned up in
teardown, so tests don't interfere with each other or leave state behind.
"""

import os
import uuid

import pytest
from falkordb.asyncio import FalkorDB

from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.models.entity import Entity
from contextstore.models.memory import Memory
from contextstore.models.provenance import Provenance
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope


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
    tid = f"test{uuid.uuid4().hex[:16]}"
    yield tid
    graph_name = f"tenant_{tid}"
    if graph_name in await store._client.list_graphs():
        await store._client.select_graph(graph_name).delete()


def make_scope(tenant_id: str, **kv: str) -> Scope:
    return Scope.from_dict({"tenant_id": tenant_id, **kv})


def make_provenance(**overrides) -> Provenance:
    defaults = dict(source="integration_test")
    defaults.update(overrides)
    return Provenance(**defaults)


async def test_health_check_true_when_reachable(store):
    assert await store.health_check() is True


async def test_write_memory_then_get_entity(store, tenant_id):
    scope = make_scope(tenant_id, user_id="u_1")
    provenance = make_provenance()
    pedro = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    memory = Memory(content="Pedro exists.", entities=[pedro], scope=scope, provenance=provenance)

    memory_id = await store.write_memory(memory)
    assert memory_id == str(memory.id)

    fetched = await store.get_entity(pedro.id, tenant_id)
    assert fetched is not None
    assert fetched.id == pedro.id
    assert fetched.name == "Pedro"
    assert fetched.entity_type == "person"
    assert fetched.scope == scope


async def test_get_entity_returns_none_when_missing(store, tenant_id):
    assert await store.get_entity(uuid.uuid4(), tenant_id) is None


async def test_write_memory_with_relation(store, tenant_id):
    scope = make_scope(tenant_id, user_id="u_1")
    provenance = make_provenance()
    pedro = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    acme = Entity(name="Acme", entity_type="org", scope=scope, provenance=provenance)
    works_at = Relation(
        source_entity_id=pedro.id,
        target_entity_id=acme.id,
        relation_type="works_at",
        scope=scope,
        provenance=provenance,
    )
    memory = Memory(
        content="Pedro works at Acme.",
        entities=[pedro, acme],
        relations=[works_at],
        scope=scope,
        provenance=provenance,
    )

    await store.write_memory(memory)

    results = await store.traverse([pedro.id], max_depth=1, scope=scope)
    assert len(results) == 1
    entity, relations = results[0]
    assert entity.id == acme.id
    assert len(relations) == 1
    assert relations[0].relation_type == "works_at"
    assert relations[0].source_entity_id == pedro.id
    assert relations[0].target_entity_id == acme.id


async def test_write_memory_relation_conflict_keeps_history_and_support_count(store, tenant_id):
    scope = make_scope(tenant_id, user_id="u_1")
    globex = Entity(name="Globex", entity_type="org", scope=scope, provenance=make_provenance())
    product_y = Entity(
        name="Product Y", entity_type="product", scope=scope, provenance=make_provenance()
    )
    await store.write_memory(
        Memory(
            content="seed entities",
            entities=[globex, product_y],
            scope=scope,
            provenance=make_provenance(),
        )
    )

    first_quote = Relation(
        source_entity_id=globex.id,
        target_entity_id=product_y.id,
        relation_type="quoted",
        properties={"price": "4.20"},
        scope=scope,
        provenance=make_provenance(source="supplier_agent"),
    )
    await store.write_memory(
        Memory(
            content="Globex quoted $4.20",
            entities=[],
            relations=[first_quote],
            scope=scope,
            provenance=make_provenance(source="supplier_agent"),
        )
    )

    second_quote = Relation(
        source_entity_id=globex.id,
        target_entity_id=product_y.id,
        relation_type="quoted",
        properties={"price": "4.50"},
        scope=scope,
        provenance=make_provenance(source="supplier_agent"),
    )
    await store.write_memory(
        Memory(
            content="Globex revised to $4.50",
            entities=[],
            relations=[second_quote],
            scope=scope,
            provenance=make_provenance(source="supplier_agent"),
        )
    )

    results = await store.traverse([globex.id], max_depth=1, scope=scope)
    _, relations = next(r for r in results if r[0].id == product_y.id)
    assert len(relations) == 1
    quoted = relations[0]

    # Same edge throughout -- id is stable, not recreated on conflict.
    assert quoted.id == first_quote.id
    # Active value reflects the latest claim ("latest wins").
    assert quoted.properties == {"price": "4.50"}
    # Full claim history is kept, old claim marked superseded, not deleted.
    assert [c.value for c in quoted.claims] == ["4.20", "4.50"]
    assert quoted.claims[1].provenance.supersedes == [str(quoted.claims[0].id)]
    assert quoted.contributing_sources == ["supplier_agent"]


async def test_find_entities_by_name_and_type(store, tenant_id):
    scope = make_scope(tenant_id, user_id="u_1")
    provenance = make_provenance()
    pedro = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    acme = Entity(name="Acme", entity_type="org", scope=scope, provenance=provenance)
    memory = Memory(
        content="Pedro and Acme.", entities=[pedro, acme], scope=scope, provenance=provenance
    )
    await store.write_memory(memory)

    by_type = await store.find_entities(scope, entity_type="org")
    assert [e.id for e in by_type] == [acme.id]

    by_name = await store.find_entities(scope, name="Pedro")
    assert [e.id for e in by_name] == [pedro.id]


async def test_find_entities_respects_scope(store, tenant_id):
    scope_a = make_scope(tenant_id, user_id="u_1")
    scope_b = make_scope(tenant_id, user_id="u_2")
    provenance = make_provenance()
    entity_a = Entity(name="OnlyA", entity_type="person", scope=scope_a, provenance=provenance)
    entity_b = Entity(name="OnlyB", entity_type="person", scope=scope_b, provenance=provenance)
    memory = Memory(
        content="two scopes",
        entities=[entity_a, entity_b],
        scope=make_scope(tenant_id, workflow="shared"),
        provenance=provenance,
    )
    await store.write_memory(memory)

    found = await store.find_entities(scope_a, name="OnlyA")
    assert [e.id for e in found] == [entity_a.id]

    not_found = await store.find_entities(scope_a, name="OnlyB")
    assert not_found == []


async def test_delete_memory_removes_its_entities(store, tenant_id):
    scope = make_scope(tenant_id, user_id="u_1")
    provenance = make_provenance()
    pedro = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    memory = Memory(content="Pedro.", entities=[pedro], scope=scope, provenance=provenance)
    memory_id = await store.write_memory(memory)

    deleted = await store.delete_memory(memory_id, tenant_id)
    assert deleted is True

    assert await store.get_entity(pedro.id, tenant_id) is None


async def test_delete_memory_returns_false_when_nothing_to_delete(store, tenant_id):
    assert await store.delete_memory(str(uuid.uuid4()), tenant_id) is False


async def test_tenant_isolation_is_structural(store, tenant_id):
    other_tenant_id = f"test{uuid.uuid4().hex[:16]}"
    scope_a = make_scope(tenant_id, user_id="u_1")
    scope_b = make_scope(other_tenant_id, user_id="u_1")
    provenance = make_provenance()

    pedro_a = Entity(name="Pedro", entity_type="person", scope=scope_a, provenance=provenance)
    pedro_b = Entity(name="Pedro", entity_type="person", scope=scope_b, provenance=provenance)

    try:
        await store.write_memory(
            Memory(content="A", entities=[pedro_a], scope=scope_a, provenance=provenance)
        )
        await store.write_memory(
            Memory(content="B", entities=[pedro_b], scope=scope_b, provenance=provenance)
        )

        # Tenant A's graph store calls never see tenant B's entity, and vice versa.
        assert await store.get_entity(pedro_b.id, tenant_id) is None
        assert await store.get_entity(pedro_a.id, other_tenant_id) is None
        assert [e.id for e in await store.find_entities(scope_a)] == [pedro_a.id]
        assert [e.id for e in await store.find_entities(scope_b)] == [pedro_b.id]
    finally:
        other_graph_name = f"tenant_{other_tenant_id}"
        if other_graph_name in await store._client.list_graphs():
            await store._client.select_graph(other_graph_name).delete()


async def test_find_similar_entities_returns_empty_for_uninitialized_tenant(store, tenant_id):
    scope = make_scope(tenant_id, user_id="u_1")
    results = await store.find_similar_entities(scope, [1.0, 0.0, 0.0, 0.0], None, 5)
    assert results == []


async def test_find_similar_entities_orders_by_similarity_descending(store, tenant_id):
    await store.ensure_graph_initialized(tenant_id, embedding_dimension=4)
    scope = make_scope(tenant_id, user_id="u_1")
    provenance = make_provenance()

    identical = Entity(
        name="Identical",
        entity_type="person",
        scope=scope,
        provenance=provenance,
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    similar = Entity(
        name="Similar",
        entity_type="person",
        scope=scope,
        provenance=provenance,
        embedding=[0.9, 0.1, 0.0, 0.0],
    )
    orthogonal = Entity(
        name="Orthogonal",
        entity_type="person",
        scope=scope,
        provenance=provenance,
        embedding=[0.0, 1.0, 0.0, 0.0],
    )
    memory = Memory(
        content="three entities",
        entities=[identical, similar, orthogonal],
        scope=scope,
        provenance=provenance,
    )
    await store.write_memory(memory)

    results = await store.find_similar_entities(scope, [1.0, 0.0, 0.0, 0.0], None, 5)

    names_in_order = [entity.name for entity, _ in results]
    assert names_in_order == ["Identical", "Similar", "Orthogonal"]

    scores = dict((entity.name, score) for entity, score in results)
    assert scores["Identical"] == pytest.approx(1.0, abs=1e-4)
    assert scores["Orthogonal"] == pytest.approx(0.0, abs=1e-4)
    assert scores["Orthogonal"] < scores["Similar"] < scores["Identical"]


async def test_find_similar_entities_filters_by_entity_type_and_scope(store, tenant_id):
    await store.ensure_graph_initialized(tenant_id, embedding_dimension=4)
    scope_a = make_scope(tenant_id, user_id="u_1")
    scope_b = make_scope(tenant_id, user_id="u_2")
    provenance = make_provenance()

    person = Entity(
        name="Pedro",
        entity_type="person",
        scope=scope_a,
        provenance=provenance,
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    org = Entity(
        name="Acme",
        entity_type="org",
        scope=scope_a,
        provenance=provenance,
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    other_scope_person = Entity(
        name="OtherUser",
        entity_type="person",
        scope=scope_b,
        provenance=provenance,
        embedding=[1.0, 0.0, 0.0, 0.0],
    )
    memory = Memory(
        content="mixed entities",
        entities=[person, org, other_scope_person],
        scope=scope_a,
        provenance=provenance,
    )
    await store.write_memory(memory)
    await store.write_memory(
        Memory(
            content="other user entity",
            entities=[],
            scope=scope_b,
            provenance=provenance,
        )
    )

    by_type = await store.find_similar_entities(scope_a, [1.0, 0.0, 0.0, 0.0], "person", 5)
    assert [e.id for e, _ in by_type] == [person.id]

    by_scope = await store.find_similar_entities(scope_a, [1.0, 0.0, 0.0, 0.0], None, 5)
    assert other_scope_person.id not in [e.id for e, _ in by_scope]


async def test_ensure_graph_initialized_is_idempotent(store, tenant_id):
    await store.ensure_graph_initialized(tenant_id, embedding_dimension=4)
    await store.ensure_graph_initialized(tenant_id, embedding_dimension=4)


# --- Admin operator support: graph_stats / drop_graph ------------------------


async def test_graph_stats_zero_for_unwritten_tenant(store, tenant_id):
    # A tenant whose graph was never written to reports (0, 0), not an error.
    assert await store.graph_stats(tenant_id) == (0, 0)


async def test_graph_stats_counts_nodes_and_edges(store, tenant_id):
    scope = make_scope(tenant_id)
    provenance = make_provenance()
    a = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    b = Entity(name="ASML", entity_type="org", scope=scope, provenance=provenance)
    relation = Relation(
        source_entity_id=a.id,
        target_entity_id=b.id,
        relation_type="works_at",
        scope=scope,
        provenance=provenance,
    )
    await store.write_memory(
        Memory(
            content="Pedro works at ASML.",
            entities=[a, b],
            relations=[relation],
            scope=scope,
            provenance=provenance,
        )
    )

    assert await store.graph_stats(tenant_id) == (2, 1)


async def test_drop_graph_wipes_tenant_and_is_idempotent(store, tenant_id):
    scope = make_scope(tenant_id)
    provenance = make_provenance()
    entity = Entity(name="Pedro", entity_type="person", scope=scope, provenance=provenance)
    await store.write_memory(
        Memory(content="Pedro exists.", entities=[entity], scope=scope, provenance=provenance)
    )
    assert await store.graph_stats(tenant_id) == (1, 0)

    await store.drop_graph(tenant_id)
    assert await store.graph_stats(tenant_id) == (0, 0)
    # Dropping an already-gone graph is a no-op, not an error.
    await store.drop_graph(tenant_id)
