"""The multi-agent coherence benchmark (Stage 2 acceptance gate).

Five named scenarios, end to end through the real write path (real Claude
extraction + real OpenAI embeddings + real FalkorDB), asserting the reified-claim
adjudicator's behaviour. Skips rather than fails when FalkorDB or the LLM/
embedding APIs aren't available -- same pattern as the other integration tests.

These are the seed of the public coherence benchmark; keep them clean and named.
"""

import os
import uuid

import pytest
from falkordb.asyncio import FalkorDB

from contextstore.core.config import get_settings
from contextstore.graph.falkordb_store import FalkorDBGraphStore
from contextstore.models.entity import Entity
from contextstore.models.fact_claim import FactClaim
from contextstore.models.relation import Relation
from contextstore.models.scope import Scope
from contextstore.core.service import remember
from contextstore.vector.embeddings import OpenAIEmbeddingProvider


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
    tid = f"coh{uuid.uuid4().hex[:16]}"
    yield tid
    graph_name = f"tenant_{tid}"
    if graph_name in await store._client.list_graphs():
        await store._client.select_graph(graph_name).delete()


@pytest.fixture
def embeddings():
    settings = get_settings()
    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimensions=settings.embedding_dimension,
    )


async def _remember(store, embeddings, scope, source: str, content: str):
    try:
        return await remember(
            content=content,
            scope=scope,
            source=source,
            graph_store=store,
            embedding_provider=embeddings,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Real LLM/embedding call failed -- check ANTHROPIC/OPENAI keys: {exc}")


async def _display(store, scope) -> tuple[dict, list[Relation]]:
    """(entities-by-id, display edges) for the tenant's live graph."""
    entities = await store.find_entities(scope)
    by_id = {e.id: e for e in entities}
    relations = await store.project_display_edges(scope)
    return by_id, relations


def _edges_to(by_id: dict, relations: list[Relation], name_token: str) -> list[Relation]:
    token = name_token.casefold()
    return [
        r
        for r in relations
        if r.target_entity_id in by_id and token in by_id[r.target_entity_id].name.casefold()
    ]


# --- two_employers_same_agent: termination + replacement -> one live employer --


async def test_two_employers_same_agent(store, embeddings, tenant_id):
    scope = Scope.from_dict({"tenant_id": tenant_id})
    await _remember(store, embeddings, scope, "agent_a", "Pedro works at ASML.")
    await _remember(
        store, embeddings, scope, "agent_a", "Pedro now works at ABN AMRO and has left ASML."
    )

    by_id, relations = await _display(store, scope)
    active = [r for r in relations if r.status == "active"]

    abn = _edges_to(by_id, active, "ABN")
    asml = _edges_to(by_id, active, "ASML")
    assert abn, f"expected an active edge to ABN AMRO; live edges: {_describe(by_id, relations)}"
    assert not asml, (
        f"expected NO active edge to ASML after the move; live edges: {_describe(by_id, relations)}"
    )


# --- disputed_employers_two_agents: cross-agent conflict -> dispute, none lost --


async def test_disputed_employers_two_agents(store, embeddings, tenant_id):
    scope = Scope.from_dict({"tenant_id": tenant_id})
    await _remember(store, embeddings, scope, "agent_a", "Pedro works at ASML.")
    await _remember(store, embeddings, scope, "agent_b", "Pedro works at Booking.")

    by_id, relations = await _display(store, scope)
    asml = _edges_to(by_id, relations, "ASML")
    booking = _edges_to(by_id, relations, "Booking")

    assert asml and booking, f"both employers must survive; live edges: {_describe(by_id, relations)}"
    # Both sides flagged disputed -- neither silently dropped, neither wins.
    assert all(r.status == "disputed" for r in asml + booking), (
        f"expected both disputed; got {_describe(by_id, relations)}"
    )


# --- corroboration: same fact, two agents -> one claim, support 2 --------------


async def test_corroboration(store, embeddings, tenant_id):
    scope = Scope.from_dict({"tenant_id": tenant_id})
    m1, _ = await _remember(store, embeddings, scope, "agent_a", "Pedro works at ASML.")
    await _remember(store, embeddings, scope, "agent_b", "Pedro works at ASML.")

    graph = store._graph_for(tenant_id)
    result = await graph.query(
        "MATCH (c:Claim) WHERE c.status = 'active' "
        "RETURN c.support_count, c.asserted_by_json"
    )
    # Exactly one active claim, asserted by both agents, support 2.
    assert len(result.result_set) == 1, f"expected one active claim, got {result.result_set}"
    support_count, asserted_by_json = result.result_set[0]
    assert support_count == 2
    assert "agent_a" in asserted_by_json and "agent_b" in asserted_by_json


# --- independent_multivalue: not all conflicts are conflicts ------------------


async def test_independent_multivalue(store, embeddings, tenant_id):
    scope = Scope.from_dict({"tenant_id": tenant_id})
    await _remember(store, embeddings, scope, "agent_a", "Pedro collaborated with Maria.")
    await _remember(store, embeddings, scope, "agent_a", "Pedro collaborated with John.")

    by_id, relations = await _display(store, scope)
    active = [r for r in relations if r.status == "active"]
    maria = _edges_to(by_id, active, "Maria")
    john = _edges_to(by_id, active, "John")
    # Both collaborations stay active -- a multi-valued relation is not a conflict.
    assert maria and john, (
        f"expected both collaborations active; live edges: {_describe(by_id, relations)}"
    )
    assert all(r.status == "active" for r in maria + john)


# --- migration: legacy direct edges -> claims, provenance preserved -----------


async def test_migration_from_legacy_edges(store, tenant_id):
    # No LLM needed: build a legacy direct-edge graph by hand, then migrate.
    from scripts.migrate_edges_to_claims import migrate_tenant

    scope = Scope.from_dict({"tenant_id": tenant_id})
    settings = get_settings()
    await store.ensure_graph_initialized(tenant_id, settings.embedding_dimension)
    graph = store._graph_for(tenant_id)

    pedro = Entity(name="Pedro", entity_type="person", scope=scope, provenance=_prov())
    asml = Entity(name="ASML", entity_type="org", scope=scope, provenance=_prov())
    for ent in (pedro, asml):
        await graph.query(
            "CREATE (n:Entity) SET n += $props",
            {"props": {"id": str(ent.id), "name": ent.name, "scope_json": _scope_json(scope)}},
        )
    edge_id = str(uuid.uuid4())
    await graph.query(
        "MATCH (a:Entity {id: $s}), (b:Entity {id: $o}) CREATE (a)-[r:works_at]->(b) SET r += $p",
        {
            "s": str(pedro.id),
            "o": str(asml.id),
            "p": {
                "id": edge_id,
                "source_entity_id": str(pedro.id),
                "target_entity_id": str(asml.id),
                "properties_json": "{}",
                "scope_json": _scope_json(scope),
                "provenance_json": _prov(source="legacy_agent").model_dump_json(),
                "claims_json": "[]",
                "contributing_sources_json": '["legacy_agent"]',
                "support_count": 3,
                "memory_id": "legacy_mem",
            },
        },
    )

    created = await migrate_tenant(store, tenant_id)
    assert created == 1

    # Legacy edge gone, claim present and projected, provenance/support preserved.
    leftover = await graph.query("MATCH (:Entity)-[r:works_at]->(:Entity) RETURN count(r)")
    assert leftover.result_set[0][0] == 0
    claims = await store.find_active_claims(scope, pedro.id, "works_at")
    assert len(claims) == 1
    claim: FactClaim = claims[0]
    assert str(claim.id) == edge_id
    assert claim.support_count == 3
    assert claim.asserted_by == ["legacy_agent"]
    edges = await store.project_display_edges(scope)
    assert len(edges) == 1 and edges[0].source_entity_id == pedro.id


# --- small helpers ------------------------------------------------------------


def _describe(by_id: dict, relations: list[Relation]) -> str:
    def name(eid):
        return by_id[eid].name if eid in by_id else str(eid)[:8]

    return ", ".join(
        f"{name(r.source_entity_id)}-[{r.relation_type}/{r.status}]->{name(r.target_entity_id)}"
        for r in relations
    )


def _prov(source: str = "test"):
    from contextstore.models.provenance import Provenance

    return Provenance(source=source)


def _scope_json(scope: Scope) -> str:
    import json

    return json.dumps(scope.to_query_dict())
