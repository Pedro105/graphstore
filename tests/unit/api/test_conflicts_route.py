"""Stage 3 acceptance (endpoint): GET /v1/conflicts surfaces live disputes with
provenance, grouped by subject+predicate, and excludes resolved (non-disputed)
facts. GraphStore + auth are mocked -- no FalkorDB, no Postgres, no LLM.
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
from contextstore.api.dependencies import get_graph_store
from contextstore.db import postgres
from contextstore.graph.store import GraphStore
from contextstore.models.entity import Entity
from contextstore.models.fact_claim import FactClaim
from contextstore.models.provenance import Provenance
from contextstore.models.scope import Scope

TENANT = "tenant_from_key"
SCOPE = Scope.from_dict({"tenant_id": TENANT})

PEDRO = Entity(name="Pedro", entity_type="person", scope=SCOPE, provenance=Provenance(source="a"))
ASML = Entity(name="ASML", entity_type="org", scope=SCOPE, provenance=Provenance(source="a"))
BOOKING = Entity(name="Booking", entity_type="org", scope=SCOPE, provenance=Provenance(source="b"))


def _disputed(object_id, asserter):
    return FactClaim(
        predicate="works_at",
        raw_predicate="works_at",
        subject_id=PEDRO.id,
        object_id=object_id,
        status="disputed",
        asserted_by=[asserter],
        scope=SCOPE,
    )


@pytest.fixture
def client(monkeypatch):
    graph_store = AsyncMock(spec=GraphStore)
    graph_store.find_entities.return_value = [PEDRO, ASML, BOOKING]

    async def fake_resolve(db, raw_key):
        if raw_key == "goodkey":
            return postgres.ResolvedKey(api_key_id=uuid4(), tenant_id=TENANT, user_id=uuid4())
        return None

    monkeypatch.setattr(postgres, "resolve_api_key", fake_resolve)
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_graph_store] = lambda: graph_store
    yield TestClient(app), graph_store
    app.dependency_overrides.clear()


def test_conflicts_groups_competing_claims_with_asserters(client):
    test_client, graph_store = client
    graph_store.find_disputed_claims.return_value = [
        _disputed(ASML.id, "agent_a"),
        _disputed(BOOKING.id, "agent_b"),
    ]

    resp = test_client.get("/v1/conflicts", headers={"Authorization": "Bearer goodkey"})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1  # grouped into one subject+predicate conflict
    conflict = body[0]
    assert conflict["subject_name"] == "Pedro"
    assert conflict["predicate"] == "works_at"
    objects = {c["object_name"] for c in conflict["claims"]}
    assert objects == {"ASML", "Booking"}
    asserters = {a for c in conflict["claims"] for a in c["asserted_by"]}
    assert asserters == {"agent_a", "agent_b"}


def test_conflicts_empty_when_nothing_disputed(client):
    test_client, graph_store = client
    graph_store.find_disputed_claims.return_value = []

    resp = test_client.get("/v1/conflicts", headers={"Authorization": "Bearer goodkey"})

    assert resp.status_code == 200
    assert resp.json() == []


def test_conflicts_requires_auth(client):
    test_client, _ = client
    resp = test_client.get("/v1/conflicts")
    assert resp.status_code in (401, 403)
