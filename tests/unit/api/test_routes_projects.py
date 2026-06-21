"""Tests for the user-facing /v1/projects endpoints through the TestClient.

Verifies project creation mints a key for the new tenant and attributes
ownership to the authenticated user (never the request body), and that listing
is scoped to the caller's own user_id. Postgres is mocked.
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

from contextstore.api.auth import get_db
from contextstore.api.dependencies import get_graph_store
from contextstore.db import postgres
from contextstore.graph.store import GraphStore

USER_ID = uuid4()


@pytest.fixture
def graph_store():
    return AsyncMock(spec=GraphStore)


@pytest.fixture
def client(monkeypatch, graph_store):
    async def fake_resolve(db, raw_key):
        if raw_key == "goodkey":
            return postgres.ResolvedKey(
                api_key_id=uuid4(), tenant_id="proj_existing", user_id=USER_ID
            )
        return None

    monkeypatch.setattr(postgres, "resolve_api_key", fake_resolve)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_graph_store] = lambda: graph_store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_project_requires_auth(client):
    assert client.post("/v1/projects", json={"name": "X"}).status_code == 401


def test_create_project_mints_key_and_owns_to_authed_user(client, monkeypatch):
    new_tenant, new_key_id = "proj_new123", uuid4()
    created = AsyncMock(
        return_value=(
            {
                "id": uuid4(),
                "tenant_id": new_tenant,
                "name": "Research",
                "description": None,
                "created_at": datetime.now(UTC),
            },
            "csk_live_brandnewkey",
            new_key_id,
        )
    )
    monkeypatch.setattr(postgres, "create_project_with_key", created)

    resp = client.post(
        "/v1/projects",
        json={"name": "Research"},
        headers={"Authorization": "Bearer goodkey"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant_id"] == new_tenant
    assert body["api_key"] == "csk_live_brandnewkey"
    # Owner is the authenticated user from the key, not anything in the body.
    assert created.await_args.args[1] == USER_ID
    assert created.await_args.args[2] == "Research"


def test_list_projects_is_scoped_to_authed_user(client, monkeypatch):
    listed = AsyncMock(
        return_value=[
            {
                "id": uuid4(),
                "tenant_id": "proj_existing",
                "name": "Default",
                "description": None,
                "created_at": datetime.now(UTC),
            }
        ]
    )
    monkeypatch.setattr(postgres, "list_projects_for_user", listed)

    resp = client.get("/v1/projects", headers={"Authorization": "Bearer goodkey"})
    assert resp.status_code == 200
    assert resp.json()[0]["tenant_id"] == "proj_existing"
    # Listing is filtered by the caller's own user_id.
    assert listed.await_args.args[1] == USER_ID


def test_rename_project_requires_auth(client):
    assert client.patch("/v1/projects/proj_x", json={"name": "X"}).status_code == 401


def test_rename_project_updates_name_for_owner(client, monkeypatch):
    renamed = AsyncMock(
        return_value={
            "id": uuid4(),
            "tenant_id": "proj_other",
            "name": "Renamed",
            "description": None,
            "created_at": datetime.now(UTC),
        }
    )
    monkeypatch.setattr(postgres, "rename_project_for_user", renamed)

    resp = client.patch(
        "/v1/projects/proj_other",
        json={"name": "Renamed"},
        headers={"Authorization": "Bearer goodkey"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    # Ownership is enforced with the authenticated user_id, not anything client-supplied.
    assert renamed.await_args.args[1:] == ("proj_other", USER_ID, "Renamed")


def test_rename_project_not_owned_is_404(client, monkeypatch):
    monkeypatch.setattr(postgres, "rename_project_for_user", AsyncMock(return_value=None))
    resp = client.patch(
        "/v1/projects/proj_someoneelse",
        json={"name": "X"},
        headers={"Authorization": "Bearer goodkey"},
    )
    assert resp.status_code == 404


def test_delete_project_wipes_pg_and_graph_for_owner(client, graph_store, monkeypatch):
    monkeypatch.setattr(
        postgres,
        "get_project_for_user",
        AsyncMock(return_value={"tenant_id": "proj_other", "owner_user_id": USER_ID, "name": "X"}),
    )
    cascade = AsyncMock(return_value=True)
    monkeypatch.setattr(postgres, "delete_project_cascade", cascade)

    resp = client.delete(
        "/v1/projects/proj_other?confirm=proj_other",
        headers={"Authorization": "Bearer goodkey"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    cascade.assert_awaited_once()
    graph_store.drop_graph.assert_awaited_once_with("proj_other")


def test_delete_project_requires_confirm(client, monkeypatch):
    monkeypatch.setattr(
        postgres,
        "get_project_for_user",
        AsyncMock(return_value={"tenant_id": "proj_other", "owner_user_id": USER_ID, "name": "X"}),
    )
    cascade = AsyncMock(return_value=True)
    monkeypatch.setattr(postgres, "delete_project_cascade", cascade)

    resp = client.delete(
        "/v1/projects/proj_other?confirm=wrong",
        headers={"Authorization": "Bearer goodkey"},
    )
    assert resp.status_code == 400
    cascade.assert_not_awaited()


def test_delete_project_not_owned_is_404(client, monkeypatch):
    monkeypatch.setattr(postgres, "get_project_for_user", AsyncMock(return_value=None))
    resp = client.delete(
        "/v1/projects/proj_someoneelse?confirm=proj_someoneelse",
        headers={"Authorization": "Bearer goodkey"},
    )
    assert resp.status_code == 404


def test_delete_refuses_the_keys_own_project(client, graph_store, monkeypatch):
    # proj_existing is the tenant the authenticated key is bound to: deleting it
    # would revoke the key mid-request, so it's refused with 409 even when owned.
    monkeypatch.setattr(
        postgres,
        "get_project_for_user",
        AsyncMock(
            return_value={"tenant_id": "proj_existing", "owner_user_id": USER_ID, "name": "X"}
        ),
    )
    cascade = AsyncMock(return_value=True)
    monkeypatch.setattr(postgres, "delete_project_cascade", cascade)

    resp = client.delete(
        "/v1/projects/proj_existing?confirm=proj_existing",
        headers={"Authorization": "Bearer goodkey"},
    )
    assert resp.status_code == 409
    cascade.assert_not_awaited()
    graph_store.drop_graph.assert_not_awaited()
