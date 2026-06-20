"""Unit tests for the projects / audit-log / admin Postgres helpers, asyncpg
fully mocked (no real database).

Covers project provisioning (project + key minted atomically in one
transaction), the memory-write audit log, the cross-tenant admin reads, and the
FK-safe deletion order of the tenant wipe.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from contextstore.db import postgres


def _async_cm(enter_value):
    """An async context manager mock whose __aenter__ yields `enter_value`."""
    cm = AsyncMock()
    cm.__aenter__.return_value = enter_value
    cm.__aexit__.return_value = False
    return cm


def _transactional_pool(conn):
    """A pool mock where `async with pool.acquire() as conn` yields `conn` and
    `async with conn.transaction():` is a no-op context. acquire()/transaction()
    are sync calls returning async context managers, matching asyncpg."""
    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=_async_cm(conn))
    conn.transaction = MagicMock(return_value=_async_cm(None))
    return pool


def test_generate_tenant_id_is_graph_name_safe_and_unique():
    import re

    tid = postgres.generate_tenant_id()
    assert tid.startswith("proj_")
    assert re.match(r"^[A-Za-z0-9_-]+$", tid)  # must be a legal FalkorDB graph name
    assert postgres.generate_tenant_id() != postgres.generate_tenant_id()


async def test_create_project_with_key_mints_key_and_is_atomic():
    owner = uuid4()
    project_id, key_id = uuid4(), uuid4()
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "id": project_id,
            "tenant_id": "ignored_db_value",
            "name": "Research",
            "description": None,
            "created_at": "t0",
        },
        {"id": key_id},
    ]
    pool = _transactional_pool(conn)

    project, raw_key, api_key_id = await postgres.create_project_with_key(
        pool, owner, "Research", None
    )

    assert raw_key.startswith(postgres.KEY_PREFIX)
    assert api_key_id == key_id
    assert project["name"] == "Research"
    # Project insert binds a freshly generated tenant_id (not anything caller-supplied),
    # and the key is created for that same tenant_id.
    project_args = conn.fetchrow.await_args_list[0].args
    key_args = conn.fetchrow.await_args_list[1].args
    generated_tenant_id = project_args[1]
    assert generated_tenant_id.startswith("proj_")
    assert key_args[2] == generated_tenant_id  # key minted for the new tenant
    # The plaintext key is never written -- only its hash.
    assert raw_key not in key_args
    assert postgres._verify_key(raw_key, key_args[3]) is True


async def test_list_projects_for_user_is_owner_scoped():
    pool = AsyncMock()
    pool.fetch.return_value = [
        {"id": uuid4(), "tenant_id": "proj_a", "name": "A", "description": None, "created_at": "t0"}
    ]
    owner = uuid4()

    projects = await postgres.list_projects_for_user(pool, owner)

    assert projects[0]["tenant_id"] == "proj_a"
    assert "WHERE owner_user_id = $1" in pool.fetch.await_args.args[0]
    assert pool.fetch.await_args.args[1] == owner


async def test_get_project_for_user_filters_on_tenant_and_owner():
    pool = AsyncMock()
    owner = uuid4()
    pool.fetchrow.return_value = {"tenant_id": "alpha", "owner_user_id": owner, "name": "Alpha"}

    project = await postgres.get_project_for_user(pool, "alpha", owner)
    assert project is not None and project["tenant_id"] == "alpha"
    query = pool.fetchrow.await_args.args[0]
    # The ownership boundary: BOTH the tenant and the owner are in the WHERE.
    assert "tenant_id = $1" in query and "owner_user_id = $2" in query
    assert pool.fetchrow.await_args.args[1] == "alpha"
    assert pool.fetchrow.await_args.args[2] == owner


async def test_get_project_for_user_returns_none_when_not_owned():
    pool = AsyncMock()
    pool.fetchrow.return_value = None  # no row matches tenant+owner
    assert await postgres.get_project_for_user(pool, "someone_elses", uuid4()) is None


async def test_record_memory_write_never_raises():
    pool = AsyncMock()
    pool.execute.side_effect = RuntimeError("db down")
    # Audit logging must not be able to fail the write it's logging.
    await postgres.record_memory_write(pool, "t1", "agent", "raw content", 3, 2)


async def test_record_memory_write_persists_counts_and_content():
    pool = AsyncMock()
    await postgres.record_memory_write(pool, "t1", "agent", "Pedro works at ASML", 3, 2)
    args = pool.execute.await_args.args
    assert "INSERT INTO memory_writes" in args[0]
    assert args[1] == "t1"
    assert args[2] == "agent"
    assert args[3] == "Pedro works at ASML"  # raw content stored verbatim
    assert args[4] == 3 and args[5] == 2


async def test_list_memory_writes_is_tenant_scoped_newest_first():
    pool = AsyncMock()
    pool.fetch.return_value = []
    await postgres.list_memory_writes(pool, "t1", limit=50)
    query = pool.fetch.await_args.args[0]
    assert "WHERE tenant_id = $1" in query
    assert "ORDER BY created_at DESC" in query
    assert pool.fetch.await_args.args[1] == "t1"


async def test_delete_memory_write_is_tenant_constrained():
    pool = AsyncMock()
    pool.execute.return_value = "DELETE 1"
    assert await postgres.delete_memory_write(pool, "t1", uuid4()) is True
    assert "tenant_id = $2" in pool.execute.await_args.args[0]

    pool.execute.return_value = "DELETE 0"  # wrong tenant / not found
    assert await postgres.delete_memory_write(pool, "t1", uuid4()) is False


async def test_list_users_with_project_counts_groups_by_user():
    pool = AsyncMock()
    pool.fetch.return_value = [
        {"id": uuid4(), "email": "a@x.com", "created_at": "t0", "project_count": 2}
    ]
    users = await postgres.list_users_with_project_counts(pool)
    assert users[0]["project_count"] == 2
    assert "LEFT JOIN projects" in pool.fetch.await_args.args[0]


async def test_list_all_projects_joins_owner_and_last_activity():
    pool = AsyncMock()
    pool.fetch.return_value = []
    await postgres.list_all_projects(pool)
    query = pool.fetch.await_args.args[0]
    assert "owner_email" in query
    assert "last_activity_at" in query
    assert "usage_log" in query


async def test_list_usage_filters_by_tenant_when_given():
    pool = AsyncMock()
    pool.fetch.return_value = []

    await postgres.list_usage(pool, tenant_id="t1", limit=10)
    assert "WHERE tenant_id = $1" in pool.fetch.await_args.args[0]
    assert pool.fetch.await_args.args[1] == "t1"

    await postgres.list_usage(pool, tenant_id=None, limit=10)
    # No tenant filter when not scoped.
    assert "WHERE tenant_id" not in pool.fetch.await_args.args[0]


async def test_writes_over_time_groups_by_day_within_window():
    pool = AsyncMock()
    pool.fetch.return_value = [{"day": "2026-06-19", "count": 4}]
    rows = await postgres.writes_over_time(pool, days=30)
    assert rows[0]["count"] == 4
    query = pool.fetch.await_args.args[0]
    assert "date_trunc('day'" in query and "make_interval(days => $1)" in query
    assert "FROM memory_writes" in query
    assert pool.fetch.await_args.args[1] == 30


async def test_tokens_over_time_sums_tokens():
    pool = AsyncMock()
    pool.fetch.return_value = [{"day": "2026-06-19", "tokens": 1200}]
    await postgres.tokens_over_time(pool, days=7)
    query = pool.fetch.await_args.args[0]
    assert "SUM(tokens_used)" in query and "FROM usage_log" in query


async def test_recall_latency_uses_percentiles_on_recall_rows_only():
    pool = AsyncMock()
    pool.fetch.return_value = [{"day": "2026-06-19", "count": 10, "p50": 42, "p95": 90}]
    rows = await postgres.recall_latency_over_time(pool, days=30)
    assert rows[0]["p95"] == 90
    query = pool.fetch.await_args.args[0]
    assert "percentile_cont(0.5)" in query and "percentile_cont(0.95)" in query
    assert "latency_ms IS NOT NULL" in query  # recall rows only


async def test_query_class_breakdown_counts_by_class():
    pool = AsyncMock()
    pool.fetch.return_value = [{"query_class": "single_hop", "count": 5}]
    await postgres.query_class_breakdown(pool, days=7)
    query = pool.fetch.await_args.args[0]
    assert "GROUP BY query_class" in query and "query_class IS NOT NULL" in query


async def test_top_projects_splits_writes_and_recalls():
    pool = AsyncMock()
    pool.fetch.return_value = [
        {"tenant_id": "alpha", "name": "Alpha", "writes": 3, "recalls": 7, "total": 10}
    ]
    rows = await postgres.top_projects_by_activity(pool, days=7)
    assert rows[0]["writes"] == 3 and rows[0]["recalls"] == 7
    query = pool.fetch.await_args.args[0]
    assert "FILTER (WHERE u.endpoint = '/v1/memories')" in query
    assert "FILTER (WHERE u.endpoint = '/v1/recall')" in query
    assert "LEFT JOIN projects" in query


async def test_project_sources_groups_by_source_with_recency():
    pool = AsyncMock()
    pool.fetch.return_value = [
        {
            "source": "agent_a",
            "write_count": 9,
            "entities": 12,
            "relations": 4,
            "last_activity_at": "t0",
        }
    ]
    rows = await postgres.project_sources(pool, "alpha")
    assert rows[0]["source"] == "agent_a" and rows[0]["write_count"] == 9
    query = pool.fetch.await_args.args[0]
    assert "GROUP BY source" in query and "MAX(created_at)" in query
    assert pool.fetch.await_args.args[1] == "alpha"


async def test_delete_project_cascade_deletes_in_fk_safe_order():
    conn = AsyncMock()
    # All deletes report success; the final projects delete drives the return.
    conn.execute.side_effect = ["DELETE 3", "DELETE 1", "DELETE 2", "DELETE 5", "DELETE 1"]
    pool = _transactional_pool(conn)

    assert await postgres.delete_project_cascade(pool, "t1") is True

    deleted_tables = [call.args[0].split()[2] for call in conn.execute.await_args_list]
    # usage_log before api_keys (usage_log references api_keys); api_keys and
    # memory_writes before projects (both reference projects).
    assert deleted_tables == ["usage_log", "agents", "api_keys", "memory_writes", "projects"]


async def test_delete_project_cascade_false_when_project_absent():
    conn = AsyncMock()
    conn.execute.side_effect = ["DELETE 0", "DELETE 0", "DELETE 0", "DELETE 0", "DELETE 0"]
    pool = _transactional_pool(conn)
    assert await postgres.delete_project_cascade(pool, "missing") is False
