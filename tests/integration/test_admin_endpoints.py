"""Integration tests for the /v1/admin/* endpoints against real Postgres +
FalkorDB, driven through the FastAPI app with TestClient.

Opt-in and conservative by design. These mutate Postgres (seed users/projects,
then wipe one of them), and the only DATABASE_URL on hand may point at a shared
database, so they are SKIPPED unless CONTEXTSTORE_RUN_ADMIN_INTEGRATION=1 is set.
Even then every row they touch is one they created (random, test-namespaced
ids), and the wipe test asserts a *second* seeded tenant is left untouched --
"destroy the right, and only the right, data".

Run with, e.g.:
    CONTEXTSTORE_RUN_ADMIN_INTEGRATION=1 \
    DATABASE_URL=postgresql://...disposable-db... \
    ADMIN_TOKEN=... uv run pytest tests/integration/test_admin_endpoints.py
"""

import os
import uuid

import pytest

RUN = os.getenv("CONTEXTSTORE_RUN_ADMIN_INTEGRATION") == "1"
pytestmark = pytest.mark.skipif(
    not RUN, reason="set CONTEXTSTORE_RUN_ADMIN_INTEGRATION=1 to run admin integration tests"
)

if RUN:  # pragma: no cover - import-time guards only matter when opted in
    from fastapi.testclient import TestClient
    from falkordb.asyncio import FalkorDB

    from contextstore.api.app import app
    from contextstore.api.auth import get_db
    from contextstore.api.dependencies import get_graph_store
    from contextstore.core.config import get_settings
    from contextstore.db import postgres
    from contextstore.graph.falkordb_store import FalkorDBGraphStore
    from contextstore.models.entity import Entity
    from contextstore.models.memory import Memory
    from contextstore.models.provenance import Provenance
    from contextstore.models.scope import Scope


def _admin_headers() -> dict[str, str]:
    token = get_settings().admin_token
    if token is None:
        pytest.skip("ADMIN_TOKEN not configured")
    return {"Authorization": f"Bearer {token.get_secret_value()}"}


@pytest.fixture
async def pool():
    settings = get_settings()
    if settings.database_url is None:
        pytest.skip("DATABASE_URL not configured")
    p = await postgres.create_pool(settings.database_url.get_secret_value())
    yield p
    await p.close()


@pytest.fixture
async def store():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    probe = FalkorDB(host=host, port=port)
    try:
        await probe.connection.ping()
    except Exception as exc:
        pytest.skip(f"FalkorDB not reachable: {exc}")
    finally:
        await probe.connection.aclose()
    s = FalkorDBGraphStore(host=host, port=port)
    yield s
    await s.aclose()


@pytest.fixture
async def seeded(pool, store):
    """Seed a user with two projects; write one memory + audit row into the
    first. Yields the ids; tears everything down afterward (best-effort)."""
    email = f"admin-int-{uuid.uuid4().hex[:12]}@example.test"
    user = await pool.fetchrow("INSERT INTO users (email) VALUES ($1) RETURNING id", email)
    user_id = user["id"]

    proj_a, _key_a, _ = await postgres.create_project_with_key(pool, user_id, "Alpha", None)
    proj_b, _key_b, _ = await postgres.create_project_with_key(pool, user_id, "Beta", None)
    tenant_a, tenant_b = proj_a["tenant_id"], proj_b["tenant_id"]

    # Write a real graph entity + audit row into tenant A (no LLM needed).
    scope = Scope.from_dict({"tenant_id": tenant_a})
    prov = Provenance(source="seed")
    entity = Entity(name="Globex", entity_type="org", scope=scope, provenance=prov)
    await store.ensure_graph_initialized(tenant_a, get_settings().embedding_dimension)
    await store.write_memory(
        Memory(content="Globex exists.", entities=[entity], scope=scope, provenance=prov)
    )
    await postgres.record_memory_write(pool, tenant_a, "seed", "Globex exists.", 1, 0)

    yield {
        "user_id": user_id,
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "entity_id": str(entity.id),
    }

    # Teardown: drop graphs and remaining rows for both tenants + the user.
    for tid in (tenant_a, tenant_b):
        await store.drop_graph(tid)
        await postgres.delete_project_cascade(pool, tid)
    await pool.execute("DELETE FROM users WHERE id = $1", user_id)


@pytest.fixture
def client(pool, store):
    app.state.db_pool = pool
    app.state.graph_store = store
    app.dependency_overrides[get_db] = lambda: pool
    app.dependency_overrides[get_graph_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_admin_requires_token(client):
    assert client.get("/v1/admin/users").status_code == 401


def test_admin_users_and_projects_list(client, seeded):
    headers = _admin_headers()
    users = client.get("/v1/admin/users", headers=headers).json()
    assert any(u["id"] == str(seeded["user_id"]) for u in users)

    projects = client.get("/v1/admin/projects", headers=headers).json()
    tenants = {p["tenant_id"] for p in projects}
    assert seeded["tenant_a"] in tenants and seeded["tenant_b"] in tenants
    alpha = next(p for p in projects if p["tenant_id"] == seeded["tenant_a"])
    assert alpha["node_count"] >= 1  # the seeded Globex entity


def test_admin_project_memories_show_raw_content(client, seeded):
    rows = client.get(
        f"/v1/admin/projects/{seeded['tenant_a']}/memories", headers=_admin_headers()
    ).json()
    assert any(r["raw_content"] == "Globex exists." for r in rows)


def test_admin_entity_claims_returns_history(client, seeded):
    resp = client.get(
        f"/v1/admin/projects/{seeded['tenant_a']}/entities/{seeded['entity_id']}/claims",
        headers=_admin_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["entity_name"] == "Globex"


def test_admin_wipe_destroys_only_target_tenant(client, seeded):
    headers = _admin_headers()
    tenant_a, tenant_b = seeded["tenant_a"], seeded["tenant_b"]

    # Confirmation required.
    assert client.delete(f"/v1/admin/projects/{tenant_a}", headers=headers).status_code == 400

    wipe = client.delete(
        f"/v1/admin/projects/{tenant_a}", params={"confirm": tenant_a}, headers=headers
    )
    assert wipe.status_code == 200

    projects = client.get("/v1/admin/projects", headers=headers).json()
    tenants = {p["tenant_id"] for p in projects}
    assert tenant_a not in tenants  # wiped
    assert tenant_b in tenants  # untouched -- only the target was destroyed
