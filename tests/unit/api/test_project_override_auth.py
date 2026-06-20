"""Security tests for the X-Project ownership override (written before the
feature — they prove the boundary).

The one rule under test: a request may act on a project OTHER than the key's
bound tenant ONLY if the authenticated user owns that project. Every other case
fails closed with 403 — never a silent fallback, never a data leak, never a 404
that would reveal whether the project exists.

Postgres and the graph/embedding backends are mocked via dependency overrides +
monkeypatch, so this exercises the real auth wiring without a database or LLM.
The negative cases matter more than the positive one.
"""

import pytest

try:
    from contextstore.api.app import app
except Exception:  # pragma: no cover - environment without ANTHROPIC/OPENAI keys
    pytest.skip("app import requires API keys in env", allow_module_level=True)

from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from contextstore.api.auth import get_db
from contextstore.api.dependencies import get_embedding_provider, get_graph_store
from contextstore.db import postgres
from contextstore.graph.store import GraphStore
from contextstore.vector.embeddings import EmbeddingProvider

# Two users, three projects. User A owns alpha + alpha2; user B owns beta.
USER_A = uuid4()
USER_B = uuid4()
KEY_A, KEY_B = "key_a", "key_b"
KEY_TENANT = {KEY_A: ("alpha", USER_A), KEY_B: ("beta", USER_B)}
OWNERSHIP = {("alpha", USER_A), ("alpha2", USER_A), ("beta", USER_B)}


@pytest.fixture
def graph_store():
    gs = AsyncMock(spec=GraphStore)
    gs.find_similar_entities.return_value = []
    gs.find_by_fulltext.return_value = []
    gs.traverse_from_seeds.return_value = ([], [], False)
    gs.find_entities.return_value = []
    return gs


@pytest.fixture
def client(monkeypatch, graph_store):
    async def fake_resolve(db, raw_key):
        if raw_key in KEY_TENANT:
            tenant, user_id = KEY_TENANT[raw_key]
            return postgres.ResolvedKey(api_key_id=uuid4(), tenant_id=tenant, user_id=user_id)
        return None

    async def fake_get_project_for_user(db, tenant_id, user_id):
        if (tenant_id, user_id) in OWNERSHIP:
            return {"tenant_id": tenant_id, "owner_user_id": user_id, "name": tenant_id}
        return None

    monkeypatch.setattr(postgres, "resolve_api_key", fake_resolve)
    # raising=False: the function doesn't exist yet (feature not built) -- this
    # lets the test be written first and fail on the assertion, not the patch.
    monkeypatch.setattr(postgres, "get_project_for_user", fake_get_project_for_user, raising=False)

    embedding = AsyncMock(spec=EmbeddingProvider)
    embedding.embed.return_value = [1.0, 0.0, 0.0, 0.0]

    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_graph_store] = lambda: graph_store
    app.dependency_overrides[get_embedding_provider] = lambda: embedding
    yield TestClient(app)
    app.dependency_overrides.clear()


def _recall(client, key, x_project=None):
    headers = {"Authorization": f"Bearer {key}"}
    if x_project is not None:
        headers["X-Project"] = x_project
    # Pin retrieval_mode so the recall path skips the (LLM) query classifier.
    return client.post(
        "/v1/recall", json={"query": "q", "retrieval_mode": "vector"}, headers=headers
    )


# --- Negative cases (the ones that matter) -----------------------------------


def test_cross_user_recall_forbidden(client):
    # User B aims at User A's project. Must be refused, with no data leaked.
    resp = _recall(client, KEY_B, x_project="alpha")
    assert resp.status_code == 403
    body = resp.text
    assert "entities" not in body and "scope" not in body  # only an error detail


def test_cross_user_memories_forbidden(client):
    resp = client.post(
        "/v1/memories",
        json={"content": "secret", "source": "x"},
        headers={"Authorization": f"Bearer {KEY_B}", "X-Project": "alpha"},
    )
    assert resp.status_code == 403


def test_cross_user_graph_forbidden(client):
    resp = client.get(
        "/v1/graph", headers={"Authorization": f"Bearer {KEY_B}", "X-Project": "alpha"}
    )
    assert resp.status_code == 403


def test_nonexistent_project_returns_403_not_404(client):
    # Don't leak whether the id exists -- same 403 as the not-owned case.
    resp = _recall(client, KEY_A, x_project="does_not_exist")
    assert resp.status_code == 403


# --- Positive / unchanged behavior -------------------------------------------


def test_no_x_project_header_unchanged(client):
    # No header -> the key's own tenant, exactly as before.
    resp = _recall(client, KEY_A)
    assert resp.status_code == 200
    assert resp.json()["scope"]["tenant_id"] == "alpha"


def test_owned_project_override_succeeds(client):
    # User A switches to their other project -> allowed, scope overridden.
    resp = _recall(client, KEY_A, x_project="alpha2")
    assert resp.status_code == 200
    assert resp.json()["scope"]["tenant_id"] == "alpha2"


def test_header_equal_to_own_tenant_is_allowed(client):
    # Selecting the key's own tenant is a no-op, not a forbidden "switch".
    resp = _recall(client, KEY_A, x_project="alpha")
    assert resp.status_code == 200
    assert resp.json()["scope"]["tenant_id"] == "alpha"
