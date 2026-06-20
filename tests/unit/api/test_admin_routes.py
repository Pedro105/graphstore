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
from contextstore.api.auth import get_db
from contextstore.api.dependencies import get_graph_store
from contextstore.db import postgres
from contextstore.graph.store import GraphStore
from contextstore.models.claim import Claim
from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope

ADMIN_TOKEN = "admintoken-for-tests"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


class _FakeSettings:
    admin_token = SecretStr(ADMIN_TOKEN)


@pytest.fixture
def pool():
    return AsyncMock()


@pytest.fixture
def graph_store():
    return AsyncMock(spec=GraphStore)


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
