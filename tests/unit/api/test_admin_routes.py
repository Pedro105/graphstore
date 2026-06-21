"""Admin API tests through FastAPI's TestClient.

Exercises the real /v1/admin route wiring -- admin-token gating, cross-tenant
reads, claim-history annotation, and the destructive guards -- with Postgres and
the graph store mocked via dependency overrides + monkeypatch. No FalkorDB,
Postgres, or LLM required.
"""

import pytest

try:
    from contextstore.api.app import app
except Exception:  # pragma: no cover - environment without ANTHROPIC/OPENAI keys
    pytest.skip("app import requires API keys in env", allow_module_level=True)

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr

from contextstore.api import auth
from contextstore.api import ratelimit
from contextstore.api.auth import get_db
from contextstore.api.dependencies import get_graph_store
from contextstore.db import postgres
from contextstore.graph.store import GraphStore
from contextstore.models.claim import Claim
from contextstore.models.entity import Entity
from contextstore.models.fact import Fact
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope

ADMIN_TOKEN = "admintoken-for-tests"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


class _FakeSettings:
    admin_token = SecretStr(ADMIN_TOKEN)
    admin_rate_limit_attempts = 5
    admin_rate_limit_window_seconds = 900


@pytest.fixture
def pool():
    return AsyncMock()


@pytest.fixture
def graph_store():
    return AsyncMock(spec=GraphStore)


@pytest.fixture(autouse=True)
def fresh_admin_limiter(monkeypatch):
    # Each test gets a clean per-IP failure limiter so accumulated failures from
    # one test can't lock out another (all TestClient requests share an IP).
    from contextstore.api.ratelimit import FailedAttemptLimiter

    monkeypatch.setattr(ratelimit, "_admin_failed_limiter", FailedAttemptLimiter())


@pytest.fixture
def client(monkeypatch, pool, graph_store):
    # Make require_admin see a configured admin token without touching real settings.
    monkeypatch.setattr(auth, "get_settings", lambda: _FakeSettings())
    app.dependency_overrides[get_db] = lambda: pool
    app.dependency_overrides[get_graph_store] = lambda: graph_store
    # No `with` -- entering the lifespan would build a real FalkorDB client; the
    # dependency overrides mean the routes never touch app.state anyway.
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Auth gating -------------------------------------------------------------


def test_admin_requires_token(client):
    assert client.get("/v1/admin/users").status_code == 401


def test_admin_rejects_wrong_token(client):
    resp = client.get("/v1/admin/users", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_admin_token_unconfigured_returns_503(client, monkeypatch):
    class _NoToken:
        admin_token = None

    monkeypatch.setattr(auth, "get_settings", lambda: _NoToken())
    assert client.get("/v1/admin/users", headers=ADMIN_HEADERS).status_code == 503


# --- Reads -------------------------------------------------------------------


def test_list_users_returns_project_counts(client, pool):
    pool.fetch.return_value = [
        {"id": uuid4(), "email": "a@x.com", "created_at": datetime.now(UTC), "project_count": 3}
    ]
    resp = client.get("/v1/admin/users", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()[0]["project_count"] == 3


def test_list_users_default_pagination_params(client, pool):
    pool.fetch.return_value = []
    resp = client.get("/v1/admin/users", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []  # out-of-range / empty page is [] / 200, not an error
    # The query is parameterised with the default limit/offset (last two args).
    assert pool.fetch.await_args.args[-2:] == (50, 0)


def test_list_users_explicit_pagination_params(client, pool):
    pool.fetch.return_value = []
    resp = client.get("/v1/admin/users?limit=25&offset=75", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert pool.fetch.await_args.args[-2:] == (25, 75)


def test_list_users_rejects_out_of_bounds_pagination(client, pool):
    pool.fetch.return_value = []
    assert client.get("/v1/admin/users?limit=0", headers=ADMIN_HEADERS).status_code == 422
    assert client.get("/v1/admin/users?limit=201", headers=ADMIN_HEADERS).status_code == 422
    assert client.get("/v1/admin/users?offset=-1", headers=ADMIN_HEADERS).status_code == 422


def test_list_admin_projects_forwards_pagination(client, pool, graph_store):
    pool.fetch.return_value = []
    resp = client.get("/v1/admin/projects?limit=10&offset=30", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert pool.fetch.await_args.args[-2:] == (10, 30)


def test_list_projects_enriches_with_live_graph_stats(client, pool, graph_store):
    pool.fetch.return_value = [
        {
            "id": uuid4(),
            "tenant_id": "proj_a",
            "name": "A",
            "description": None,
            "created_at": datetime.now(UTC),
            "owner_user_id": uuid4(),
            "owner_email": "a@x.com",
            "last_activity_at": None,
        }
    ]
    graph_store.graph_stats.return_value = (7, 4)
    resp = client.get("/v1/admin/projects", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()[0]
    assert body["node_count"] == 7 and body["edge_count"] == 4
    graph_store.graph_stats.assert_awaited_with("proj_a")


def test_project_memories_returns_raw_content(client, pool):
    pool.fetch.return_value = [
        {
            "id": uuid4(),
            "tenant_id": "proj_a",
            "source": "agent",
            "raw_content": "Pedro works at ASML",
            "extracted_entity_count": 2,
            "extracted_relation_count": 1,
            "created_at": datetime.now(UTC),
        }
    ]
    resp = client.get("/v1/admin/projects/proj_a/memories", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()[0]["raw_content"] == "Pedro works at ASML"


# --- Claim history -----------------------------------------------------------


def _entity_with_superseded_claim():
    scope = Scope.from_dict({"tenant_id": "proj_a"})
    older = Claim(
        property_name="price",
        value=10,
        provenance=Provenance(source="agent_a", created_at=datetime(2026, 1, 1, tzinfo=UTC)),
    )
    newer = Claim(
        property_name="price",
        value=20,
        provenance=Provenance(
            source="agent_b",
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
            supersedes=[str(older.id)],
        ),
    )
    return Entity(
        name="Globex",
        entity_type="Organization",
        scope=scope,
        provenance=newer.provenance,
        claims=[newer, older],  # deliberately out of order to test sorting
    )


def test_entity_claims_returns_full_history_with_supersession(client, graph_store):
    entity = _entity_with_superseded_claim()
    graph_store.get_entity.return_value = entity

    resp = client.get(
        f"/v1/admin/projects/proj_a/entities/{entity.id}/claims", headers=ADMIN_HEADERS
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity_name"] == "Globex"
    claims = body["claims"]
    assert len(claims) == 2
    # Oldest first, and the superseded claim flagged -- the full history, not
    # just the active value.
    assert claims[0]["claim"]["value"] == 10 and claims[0]["superseded"] is True
    assert claims[1]["claim"]["value"] == 20 and claims[1]["superseded"] is False


def test_entity_claims_404_when_entity_missing(client, graph_store):
    graph_store.get_entity.return_value = None
    resp = client.get(f"/v1/admin/projects/proj_a/entities/{uuid4()}/claims", headers=ADMIN_HEADERS)
    assert resp.status_code == 404


# --- Destructive guards ------------------------------------------------------


def test_wipe_requires_matching_confirm(client, pool, graph_store):
    # No confirm -> 400, and nothing is dropped.
    resp = client.delete("/v1/admin/projects/proj_a", headers=ADMIN_HEADERS)
    assert resp.status_code == 400
    graph_store.drop_graph.assert_not_called()


def test_wipe_deletes_postgres_then_graph(client, pool, graph_store, monkeypatch):
    monkeypatch.setattr(
        postgres,
        "get_project_by_tenant",
        AsyncMock(
            return_value={
                "id": uuid4(),
                "owner_user_id": uuid4(),
                "tenant_id": "proj_a",
            }
        ),
    )
    cascade = AsyncMock(return_value=True)
    monkeypatch.setattr(postgres, "delete_project_cascade", cascade)

    resp = client.delete(
        "/v1/admin/projects/proj_a", params={"confirm": "proj_a"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "wiped"
    cascade.assert_awaited_once()
    graph_store.drop_graph.assert_awaited_once_with("proj_a")


def test_wipe_404_when_project_missing(client, monkeypatch, graph_store):
    monkeypatch.setattr(postgres, "get_project_by_tenant", AsyncMock(return_value=None))
    resp = client.delete(
        "/v1/admin/projects/missing", params={"confirm": "missing"}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 404
    graph_store.drop_graph.assert_not_called()


def test_revoke_any_key_admin_override(client, pool, monkeypatch):
    monkeypatch.setattr(postgres, "revoke_api_key", AsyncMock(return_value=True))
    key_id = uuid4()
    resp = client.delete(f"/v1/admin/api-keys/{key_id}", headers=ADMIN_HEADERS)
    assert resp.status_code == 204


def test_revoke_any_key_404_when_absent(client, monkeypatch):
    monkeypatch.setattr(postgres, "revoke_api_key", AsyncMock(return_value=False))
    resp = client.delete(f"/v1/admin/api-keys/{uuid4()}", headers=ADMIN_HEADERS)
    assert resp.status_code == 404


# --- Admin brute-force lockout (through the real require_admin dependency) ----


def test_admin_auth_validation_endpoint(client):
    # The frontend validates the token against this before mounting any data page.
    resp = client.get("/v1/admin/auth", headers=ADMIN_HEADERS)
    assert resp.status_code == 200 and resp.json() == {"ok": True}


def test_repeated_failures_lock_out_even_a_correct_token(client):
    # 5 wrong tokens (the default threshold) exhaust the limit...
    for _ in range(5):
        assert (
            client.get("/v1/admin/users", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )
    # ...the 6th attempt is locked out (429) -- and crucially, even the CORRECT
    # token is now refused, so there's no timing oracle for the attacker.
    resp = client.get("/v1/admin/users", headers=ADMIN_HEADERS)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_lockout_is_per_ip(client, pool):
    pool.fetch.return_value = []  # the unaffected IP's request reaches list_users
    # Lock out the default TestClient IP.
    for _ in range(5):
        client.get("/v1/admin/users", headers={"Authorization": "Bearer wrong"})
    assert client.get("/v1/admin/users", headers=ADMIN_HEADERS).status_code == 429
    # A request from a different IP (via X-Forwarded-For) is unaffected.
    resp = client.get(
        "/v1/admin/users",
        headers={**ADMIN_HEADERS, "X-Forwarded-For": "203.0.113.9"},
    )
    assert resp.status_code == 200


# --- Analytics & sources -----------------------------------------------------


def test_analytics_composes_all_series(client, monkeypatch):
    monkeypatch.setattr(
        postgres, "writes_over_time", AsyncMock(return_value=[{"day": "2026-06-19", "count": 4}])
    )
    monkeypatch.setattr(
        postgres, "tokens_over_time", AsyncMock(return_value=[{"day": "2026-06-19", "tokens": 99}])
    )
    monkeypatch.setattr(
        postgres,
        "recall_latency_over_time",
        AsyncMock(return_value=[{"day": "2026-06-19", "count": 2, "p50": 40, "p95": 88}]),
    )
    monkeypatch.setattr(
        postgres,
        "query_class_breakdown",
        AsyncMock(return_value=[{"query_class": "single_hop", "count": 2}]),
    )
    monkeypatch.setattr(
        postgres,
        "top_projects_by_activity",
        AsyncMock(
            return_value=[
                {"tenant_id": "alpha", "name": "Alpha", "writes": 1, "recalls": 1, "total": 2}
            ]
        ),
    )
    resp = client.get("/v1/admin/analytics", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["writes_over_time"][0]["count"] == 4
    assert body["tokens_over_time"][0]["tokens"] == 99
    assert body["recall_latency"][0]["p95"] == 88
    assert body["query_class_breakdown"][0]["query_class"] == "single_hop"
    assert body["top_projects"][0]["total"] == 2


def test_project_sources_breakdown(client, pool):
    pool.fetch.return_value = [
        {
            "source": "agent_a",
            "write_count": 9,
            "entities": 12,
            "relations": 4,
            "last_activity_at": datetime.now(UTC),
        }
    ]
    resp = client.get("/v1/admin/projects/alpha/sources", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json()[0]["source"] == "agent_a"


# --- Facts table -------------------------------------------------------------


def _fact(name, value, source, day, superseded=False):
    return Fact(
        tenant_id="alpha",
        entity_id=uuid4(),
        entity_name=name,
        entity_type="org",
        property_name="price",
        value=value,
        source=source,
        asserted_at=datetime(2026, day, 1, tzinfo=UTC),
        superseded=superseded,
    )


@pytest.fixture
def facts_client(client, graph_store):
    # One page of facts; total_nodes small so the gather loop stops after one page.
    facts = [
        _fact("Globex", "100", "agent_v1", 1, superseded=True),
        _fact("Globex", "120", "agent_v2", 3, superseded=False),
        _fact("Acme", "manufacturing", "agent_v1", 2, superseded=False),
    ]
    graph_store.fetch_entity_claims_page.return_value = (facts, 3)
    return client


def test_facts_default_hides_superseded(facts_client):
    resp = facts_client.get("/v1/admin/facts?tenant_id=alpha", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    values = [f["value"] for f in body["facts"]]
    assert "100" not in values  # the superseded claim is hidden by default
    assert body["total"] == 2


def test_facts_include_superseded_toggle(facts_client):
    resp = facts_client.get(
        "/v1/admin/facts?tenant_id=alpha&include_superseded=true", headers=ADMIN_HEADERS
    )
    body = resp.json()
    assert body["total"] == 3
    assert any(f["value"] == "100" and f["superseded"] for f in body["facts"])


def test_facts_sorted_by_recency(facts_client):
    resp = facts_client.get(
        "/v1/admin/facts?tenant_id=alpha&include_superseded=true", headers=ADMIN_HEADERS
    )
    days = [f["asserted_at"][:7] for f in resp.json()["facts"]]
    assert days == sorted(days, reverse=True)  # newest first


def test_facts_filter_by_source(facts_client):
    resp = facts_client.get(
        "/v1/admin/facts?tenant_id=alpha&source=agent_v2", headers=ADMIN_HEADERS
    )
    body = resp.json()
    assert body["total"] == 1 and body["facts"][0]["source"] == "agent_v2"


def test_facts_substring_search(facts_client):
    resp = facts_client.get(
        "/v1/admin/facts?tenant_id=alpha&q=acme&include_superseded=true", headers=ADMIN_HEADERS
    )
    body = resp.json()
    assert body["total"] == 1 and body["facts"][0]["entity_name"] == "Acme"


def test_facts_pagination(facts_client):
    resp = facts_client.get(
        "/v1/admin/facts?tenant_id=alpha&include_superseded=true&page=1&page_size=2",
        headers=ADMIN_HEADERS,
    )
    body = resp.json()
    assert len(body["facts"]) == 2 and body["total"] == 3 and body["page"] == 1
