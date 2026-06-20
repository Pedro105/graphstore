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
from contextstore.db import postgres

USER_ID = uuid4()


@pytest.fixture
def client(monkeypatch):
    async def fake_resolve(db, raw_key):
        if raw_key == "goodkey":
            return postgres.ResolvedKey(
                api_key_id=uuid4(), tenant_id="proj_existing", user_id=USER_ID
            )
        return None

    monkeypatch.setattr(postgres, "resolve_api_key", fake_resolve)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
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
