"""API-level auth tests through FastAPI's TestClient.

The asyncpg lookup and the graph/embedding backends are mocked via dependency
overrides + monkeypatch, so this exercises the real route wiring (auth ->
scope construction -> recall) without FalkorDB, Postgres, or an LLM. The app
import is skipped if the environment lacks the API keys Settings requires at
import time.
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
from contextstore.models.entity import Entity
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope
from contextstore.vector.embeddings import EmbeddingProvider

TENANT_FROM_KEY = "tenant_from_key"


@pytest.fixture
def client(monkeypatch):
    scope = Scope.from_dict({"tenant_id": TENANT_FROM_KEY})
    entity = Entity(
        name="Acme Corp",
        entity_type="Organization",
        scope=scope,
        provenance=Provenance(source="seed"),
    )

    graph_store = AsyncMock(spec=GraphStore)
    graph_store.find_similar_entities.return_value = [(entity, 0.95)]
    graph_store.find_by_fulltext.return_value = []
    graph_store.traverse_from_seeds.return_value = ([entity], [], False)

    embedding_provider = AsyncMock(spec=EmbeddingProvider)
    embedding_provider.embed.return_value = [1.0, 0.0, 0.0, 0.0]

    async def fake_resolve(db, raw_key):
        if raw_key == "goodkey":
            return postgres.ResolvedKey(
                api_key_id=uuid4(), tenant_id=TENANT_FROM_KEY, user_id=uuid4()
            )
        return None

    monkeypatch.setattr(postgres, "resolve_api_key", fake_resolve)

    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_graph_store] = lambda: graph_store
    app.dependency_overrides[get_embedding_provider] = lambda: embedding_provider
    yield TestClient(app)
    app.dependency_overrides.clear()


def _recall_body(**extra):
    # Pin routing so no classifier/LLM runs.
    return {"query": "acme", "retrieval_mode": "vector", "traversal_depth": 1, **extra}


def test_recall_without_auth_header_401(client):
    response = client.post("/v1/recall", json=_recall_body())
    assert response.status_code == 401


def test_recall_with_invalid_key_401(client):
    response = client.post(
        "/v1/recall", json=_recall_body(), headers={"Authorization": "Bearer badkey"}
    )
    assert response.status_code == 401


def test_recall_with_valid_key_derives_tenant_from_auth(client):
    response = client.post(
        "/v1/recall", json=_recall_body(), headers={"Authorization": "Bearer goodkey"}
    )
    assert response.status_code == 200
    assert response.json()["scope"]["tenant_id"] == TENANT_FROM_KEY


def test_caller_cannot_spoof_tenant_via_extra_scope(client):
    response = client.post(
        "/v1/recall",
        json=_recall_body(extra_scope={"tenant_id": "evil_tenant", "user_id": "u1"}),
        headers={"Authorization": "Bearer goodkey"},
    )
    assert response.status_code == 200
    result_scope = response.json()["scope"]
    # tenant is the auth tenant, the smuggled one is dropped; other keys survive.
    assert result_scope["tenant_id"] == TENANT_FROM_KEY
    assert result_scope.get("user_id") == "u1"


def test_keys_endpoint_requires_admin_token(client):
    # No admin token configured in the test env -> management endpoints closed.
    response = client.post(
        "/v1/keys",
        json={"user_id": str(uuid4()), "tenant_id": "acme", "name": "dev"},
    )
    assert response.status_code in (401, 503)
