"""Async Postgres access for auth: API-key resolution, key management, and
usage logging. asyncpg directly -- no ORM, matching the codebase's lean,
async-by-default style.

API keys are high-entropy random tokens (`csk_live_...`) shown to the operator
once at creation and never stored; only a bcrypt hash of the key lives in
`api_keys.key_hash`. Because bcrypt is salted, the stored hash is not a
deterministic function of the key, so a key can't be looked up by an equality
match on `key_hash` -- `resolve_api_key` instead scans the (small) set of
active keys and `bcrypt.checkpw`s each. This is correct and fine at the current
solo / single-instance scale; if the active-key count ever grows large, switch
the lookup column to a deterministic keyed hash (HMAC-SHA256 with a server-side
pepper) so the existing `api_keys(key_hash)` index gives an O(1) lookup again.
The pool, key generation, and hashing are otherwise independent of that choice.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

import asyncpg
import bcrypt
import structlog

logger = structlog.get_logger()

# Prefix on every issued key so it's identifiable in logs/leaks ("csk" =
# ContextStore key, "live" leaves room for a future "test" environment).
KEY_PREFIX = "csk_live_"

# asyncpg is untyped (see mypy override), so this resolves to Any; the alias
# keeps call sites self-documenting about what they expect.
Pool: TypeAlias = asyncpg.Pool


@dataclass(frozen=True)
class ResolvedKey:
    """A successfully authenticated API key: which key, the tenant it grants
    access to, and the user that owns it. tenant_id is authoritative -- it comes
    from Postgres, not from the caller. user_id lets user-facing endpoints
    (e.g. project creation) attribute work to the owning user without trusting
    anything in the request body."""

    api_key_id: UUID
    tenant_id: str
    user_id: UUID


def generate_api_key() -> str:
    """A new random API key. Returned to the operator once; only its hash is
    persisted."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_key(raw_key: str) -> str:
    return bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_key(raw_key: str, key_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_key.encode("utf-8"), key_hash.encode("utf-8"))
    except ValueError:
        # Malformed/legacy hash in the column -- treat as a non-match, not a crash.
        return False


async def create_pool(dsn: str) -> Pool:
    """Open the connection pool. Called once from the app lifespan."""
    return await asyncpg.create_pool(dsn=dsn)


async def resolve_api_key(pool: Pool, raw_key: str) -> ResolvedKey | None:
    """Resolve a raw API key to its (api_key_id, tenant_id), or None if the key
    is invalid or revoked. Touches `last_used_at` on a successful match.

    Scans active keys and bcrypt-verifies each (see module docstring for why a
    direct hash lookup isn't possible with bcrypt).
    """
    rows = await pool.fetch(
        "SELECT id, tenant_id, user_id, key_hash FROM api_keys WHERE revoked_at IS NULL"
    )
    for row in rows:
        if _verify_key(raw_key, row["key_hash"]):
            await pool.execute("UPDATE api_keys SET last_used_at = NOW() WHERE id = $1", row["id"])
            return ResolvedKey(
                api_key_id=row["id"], tenant_id=row["tenant_id"], user_id=row["user_id"]
            )
    return None


async def get_tenant_id_for_key(pool: Pool, raw_key: str) -> str | None:
    """Tenant a valid, non-revoked key resolves to, else None. Thin wrapper over
    `resolve_api_key` for callers that only need the tenant."""
    resolved = await resolve_api_key(pool, raw_key)
    return resolved.tenant_id if resolved else None


async def log_usage(
    pool: Pool,
    api_key_id: UUID,
    tenant_id: str,
    endpoint: str,
    tokens_used: int | None = None,
    latency_ms: int | None = None,
    query_class: str | None = None,
) -> None:
    """Fire-and-forget usage record. Never raises -- usage accounting must not
    be able to fail a request.

    `latency_ms`/`query_class` are recall-only (from RetrievalStats); the write
    path leaves them None. They feed the admin latency/query-class analytics."""
    try:
        await pool.execute(
            "INSERT INTO usage_log "
            "(api_key_id, tenant_id, endpoint, tokens_used, latency_ms, query_class) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            api_key_id,
            tenant_id,
            endpoint,
            tokens_used,
            latency_ms,
            query_class,
        )
    except Exception as exc:
        logger.warning("usage_log.insert_failed", endpoint=endpoint, error=str(exc))


async def create_api_key(
    pool: Pool, user_id: UUID, tenant_id: str, name: str | None
) -> tuple[str, UUID]:
    """Mint a new key for a user/tenant. Returns (raw_key, api_key_id); the raw
    key is the only time the plaintext exists -- store nothing but its hash."""
    raw_key = generate_api_key()
    row = await pool.fetchrow(
        "INSERT INTO api_keys (user_id, tenant_id, key_hash, name) "
        "VALUES ($1, $2, $3, $4) RETURNING id",
        user_id,
        tenant_id,
        hash_key(raw_key),
        name,
    )
    assert row is not None  # INSERT ... RETURNING always yields a row
    api_key_id: UUID = row["id"]
    return raw_key, api_key_id


async def revoke_api_key(pool: Pool, key_id: UUID) -> bool:
    """Revoke an active key. Returns True if a key was revoked, False if it
    didn't exist or was already revoked."""
    result = await pool.execute(
        "UPDATE api_keys SET revoked_at = NOW() WHERE id = $1 AND revoked_at IS NULL",
        key_id,
    )
    # asyncpg returns the command tag, e.g. "UPDATE 1" / "UPDATE 0".
    return bool(result.rsplit(" ", 1)[-1] != "0")


def _command_succeeded(command_tag: str) -> bool:
    """True if an asyncpg UPDATE/DELETE command tag affected at least one row."""
    return command_tag.rsplit(" ", 1)[-1] != "0"


async def list_api_keys(pool: Pool, tenant_id: str) -> list[dict[str, Any]]:
    """Safe metadata for a tenant's keys -- never the hash or raw key."""
    rows = await pool.fetch(
        "SELECT id, name, created_at, last_used_at, revoked_at FROM api_keys "
        "WHERE tenant_id = $1 ORDER BY created_at",
        tenant_id,
    )
    return [dict(row) for row in rows]


async def revoke_api_key_for_tenant(pool: Pool, key_id: UUID, tenant_id: str) -> bool:
    """Revoke a key only if it belongs to `tenant_id` -- a tenant can revoke its
    own keys but not another tenant's. Returns False if not found, already
    revoked, or owned by a different tenant."""
    result = await pool.execute(
        "UPDATE api_keys SET revoked_at = NOW() "
        "WHERE id = $1 AND tenant_id = $2 AND revoked_at IS NULL",
        key_id,
        tenant_id,
    )
    return _command_succeeded(result)


# --- Agents (a per-tenant registry of named writers) -------------------------


async def create_agent(
    pool: Pool, tenant_id: str, name: str, description: str | None
) -> dict[str, Any]:
    row = await pool.fetchrow(
        "INSERT INTO agents (tenant_id, name, description) VALUES ($1, $2, $3) "
        "RETURNING id, name, description, created_at",
        tenant_id,
        name,
        description,
    )
    assert row is not None  # INSERT ... RETURNING always yields a row
    return dict(row)


async def list_agents(
    pool: Pool, tenant_id: str, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        "SELECT id, name, description, created_at FROM agents "
        "WHERE tenant_id = $1 ORDER BY created_at LIMIT $2 OFFSET $3",
        tenant_id,
        limit,
        offset,
    )
    return [dict(row) for row in rows]


async def delete_agent(pool: Pool, tenant_id: str, agent_id: UUID) -> bool:
    """Delete a tenant's agent. Returns False if it doesn't exist or belongs to
    a different tenant."""
    result = await pool.execute(
        "DELETE FROM agents WHERE id = $1 AND tenant_id = $2",
        agent_id,
        tenant_id,
    )
    return _command_succeeded(result)


# --- Projects (a user-owned tenant_id = one FalkorDB graph) -------------------

# Generated tenant_ids must satisfy the graph-name charset (^[A-Za-z0-9_-]+$),
# since tenant_id is used directly as a FalkorDB graph name; hex tokens do.
_TENANT_ID_PREFIX = "proj_"


def generate_tenant_id() -> str:
    """A fresh, graph-name-safe tenant_id for a new project."""
    return f"{_TENANT_ID_PREFIX}{secrets.token_hex(8)}"


async def create_project_with_key(
    pool: Pool, owner_user_id: UUID, name: str, description: str | None
) -> tuple[dict[str, Any], str, UUID]:
    """Provision a new project for a user and mint its first API key, atomically.

    A project is born with a freshly generated tenant_id (its own FalkorDB
    graph) and an API key scoped to it, so the user can write to the new graph
    immediately -- switching projects means switching keys. Returns
    (project_row, raw_key, api_key_id); the raw key is shown once and never
    stored (only its hash). Both inserts share one transaction so a failure
    can't leave a project with no key or a key with no project.
    """
    tenant_id = generate_tenant_id()
    raw_key = generate_api_key()
    async with pool.acquire() as conn:
        async with conn.transaction():
            project = await conn.fetchrow(
                "INSERT INTO projects (tenant_id, owner_user_id, name, description) "
                "VALUES ($1, $2, $3, $4) "
                "RETURNING id, tenant_id, name, description, created_at",
                tenant_id,
                owner_user_id,
                name,
                description,
            )
            key = await conn.fetchrow(
                "INSERT INTO api_keys (user_id, tenant_id, key_hash, name) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                owner_user_id,
                tenant_id,
                hash_key(raw_key),
                f"{name} default key",
            )
    assert project is not None and key is not None  # INSERT ... RETURNING
    return dict(project), raw_key, key["id"]


async def list_projects_for_user(
    pool: Pool, owner_user_id: UUID, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """The authenticated user's own projects, newest first (one page)."""
    rows = await pool.fetch(
        "SELECT id, tenant_id, name, description, created_at FROM projects "
        "WHERE owner_user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
        owner_user_id,
        limit,
        offset,
    )
    return [dict(row) for row in rows]


async def get_project_by_tenant(pool: Pool, tenant_id: str) -> dict[str, Any] | None:
    row = await pool.fetchrow(
        "SELECT id, tenant_id, owner_user_id, name, description, created_at FROM projects "
        "WHERE tenant_id = $1",
        tenant_id,
    )
    return dict(row) if row else None


async def get_project_for_user(
    pool: Pool, tenant_id: str, owner_user_id: UUID
) -> dict[str, Any] | None:
    """The project with this tenant_id, but only if `owner_user_id` owns it.

    The ownership gate for the X-Project request override (api/auth.py): the
    single WHERE clause filtering on BOTH tenant_id and owner_user_id is the
    whole security boundary -- it returns a row only when the authenticated user
    actually owns the requested project, so a non-owner (or a nonexistent
    project) is indistinguishable here, both yielding None. Callers must treat
    None as "deny" (403), never as a reason to fall back to another tenant."""
    row = await pool.fetchrow(
        "SELECT tenant_id, owner_user_id, name FROM projects "
        "WHERE tenant_id = $1 AND owner_user_id = $2",
        tenant_id,
        owner_user_id,
    )
    return dict(row) if row else None


async def rename_project_for_user(
    pool: Pool, tenant_id: str, owner_user_id: UUID, name: str
) -> dict[str, Any] | None:
    """Rename a project the user owns, returning the updated row (or None if the
    user doesn't own it / it doesn't exist).

    Ownership is the WHERE clause, same boundary as get_project_for_user: the
    UPDATE only touches a row when owner_user_id matches, so a non-owner gets
    None (treated as 404 by the caller), never a silent no-op success."""
    row = await pool.fetchrow(
        "UPDATE projects SET name = $3 WHERE tenant_id = $1 AND owner_user_id = $2 "
        "RETURNING id, tenant_id, name, description, created_at",
        tenant_id,
        owner_user_id,
        name,
    )
    return dict(row) if row else None


# --- Memory write audit log (raw content the graph engine discards) ----------


async def record_memory_write(
    pool: Pool,
    tenant_id: str,
    source: str,
    raw_content: str,
    extracted_entity_count: int,
    extracted_relation_count: int,
) -> None:
    """Append an audit row for one /v1/memories POST. Best-effort and never
    raises -- the audit log must not be able to fail a write (same contract as
    log_usage). Decoupled from the graph write entirely."""
    try:
        await pool.execute(
            "INSERT INTO memory_writes "
            "(tenant_id, source, raw_content, extracted_entity_count, extracted_relation_count) "
            "VALUES ($1, $2, $3, $4, $5)",
            tenant_id,
            source,
            raw_content,
            extracted_entity_count,
            extracted_relation_count,
        )
    except Exception as exc:
        logger.warning("memory_writes.insert_failed", tenant_id=tenant_id, error=str(exc))


async def list_memory_writes(pool: Pool, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Recent audit rows for one tenant, newest first."""
    rows = await pool.fetch(
        "SELECT id, tenant_id, source, raw_content, extracted_entity_count, "
        "extracted_relation_count, created_at FROM memory_writes "
        "WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2",
        tenant_id,
        limit,
    )
    return [dict(row) for row in rows]


async def delete_memory_write(pool: Pool, tenant_id: str, memory_write_id: UUID) -> bool:
    """Hard-delete one audit row, constrained to its tenant. Returns False if it
    doesn't exist or belongs to another tenant. Note: this removes only the
    audit record -- it does NOT un-write anything in the graph."""
    result = await pool.execute(
        "DELETE FROM memory_writes WHERE id = $1 AND tenant_id = $2",
        memory_write_id,
        tenant_id,
    )
    return _command_succeeded(result)


# --- Operator admin: cross-tenant reads + destructive wipes ------------------


async def list_users_with_project_counts(
    pool: Pool, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """Every user with how many projects they own (admin overview), one page."""
    rows = await pool.fetch(
        "SELECT u.id, u.email, u.created_at, COUNT(p.id) AS project_count "
        "FROM users u LEFT JOIN projects p ON p.owner_user_id = u.id "
        "GROUP BY u.id, u.email, u.created_at ORDER BY u.created_at LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    return [dict(row) for row in rows]


async def list_all_projects(pool: Pool, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Every project across all users, with owner email and last-activity
    timestamp from usage_log, one page. Live graph node/edge counts are NOT
    joined here (they live in FalkorDB, per tenant) -- the admin route layers
    those on."""
    rows = await pool.fetch(
        "SELECT p.id, p.tenant_id, p.name, p.description, p.created_at, "
        "p.owner_user_id, u.email AS owner_email, "
        "(SELECT MAX(created_at) FROM usage_log WHERE tenant_id = p.tenant_id) "
        "AS last_activity_at "
        "FROM projects p JOIN users u ON u.id = p.owner_user_id "
        "ORDER BY p.created_at DESC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    return [dict(row) for row in rows]


async def list_usage(
    pool: Pool, tenant_id: str | None = None, limit: int = 500
) -> list[dict[str, Any]]:
    """Usage-log rows across all tenants (or one, if `tenant_id` is given),
    newest first, with token counts and endpoint for cost breakdowns."""
    if tenant_id is not None:
        rows = await pool.fetch(
            "SELECT id, api_key_id, tenant_id, endpoint, tokens_used, created_at "
            "FROM usage_log WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2",
            tenant_id,
            limit,
        )
    else:
        rows = await pool.fetch(
            "SELECT id, api_key_id, tenant_id, endpoint, tokens_used, created_at "
            "FROM usage_log ORDER BY created_at DESC LIMIT $1",
            limit,
        )
    return [dict(row) for row in rows]


# --- Time-series & breakdown analytics ---------------------------------------
#
# All grouped by day in UTC via date_trunc; the "last N days" window uses
# make_interval so the period is a bound parameter, not string-built SQL.
#
# Each takes an optional `tenant_id`: None means cross-tenant (the operator
# admin overview), a value scopes the aggregate to one project (the user-facing
# dashboard). The tenant filter is an extra bound parameter, never string-built,
# so both call sites share one query shape with no SQL injection surface.


async def writes_over_time(
    pool: Pool, days: int = 30, tenant_id: str | None = None
) -> list[dict[str, Any]]:
    """Daily count of memory writes over the last `days` days (newest last).
    Scoped to `tenant_id` when given, else across all tenants."""
    rows = await pool.fetch(
        "SELECT date_trunc('day', created_at)::date AS day, COUNT(*) AS count "
        "FROM memory_writes "
        "WHERE created_at >= NOW() - make_interval(days => $1) "
        "AND ($2::text IS NULL OR tenant_id = $2) "
        "GROUP BY day ORDER BY day",
        days,
        tenant_id,
    )
    return [dict(row) for row in rows]


async def tokens_over_time(
    pool: Pool, days: int = 30, tenant_id: str | None = None
) -> list[dict[str, Any]]:
    """Daily sum of tokens_used (LLM spend) over the last `days` days.
    Scoped to `tenant_id` when given, else across all tenants."""
    rows = await pool.fetch(
        "SELECT date_trunc('day', created_at)::date AS day, "
        "COALESCE(SUM(tokens_used), 0)::bigint AS tokens "
        "FROM usage_log "
        "WHERE created_at >= NOW() - make_interval(days => $1) "
        "AND ($2::text IS NULL OR tenant_id = $2) "
        "GROUP BY day ORDER BY day",
        days,
        tenant_id,
    )
    return [dict(row) for row in rows]


async def recall_latency_over_time(
    pool: Pool, days: int = 30, tenant_id: str | None = None
) -> list[dict[str, Any]]:
    """Daily recall latency p50/p95 (and count) over the last `days` days.

    Only rows with a latency_ms (i.e. /v1/recall) participate; percentiles use
    Postgres percentile_cont over the day's latencies. Scoped to `tenant_id`
    when given, else across all tenants."""
    rows = await pool.fetch(
        "SELECT date_trunc('day', created_at)::date AS day, COUNT(*) AS count, "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)::int AS p50, "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::int AS p95 "
        "FROM usage_log "
        "WHERE latency_ms IS NOT NULL AND created_at >= NOW() - make_interval(days => $1) "
        "AND ($2::text IS NULL OR tenant_id = $2) "
        "GROUP BY day ORDER BY day",
        days,
        tenant_id,
    )
    return [dict(row) for row in rows]


async def query_class_breakdown(
    pool: Pool, days: int = 7, tenant_id: str | None = None
) -> list[dict[str, Any]]:
    """Count of recalls per query_class over the last `days` days, busiest first.
    Scoped to `tenant_id` when given, else across all tenants."""
    rows = await pool.fetch(
        "SELECT query_class, COUNT(*) AS count FROM usage_log "
        "WHERE query_class IS NOT NULL AND created_at >= NOW() - make_interval(days => $1) "
        "AND ($2::text IS NULL OR tenant_id = $2) "
        "GROUP BY query_class ORDER BY count DESC",
        days,
        tenant_id,
    )
    return [dict(row) for row in rows]


async def top_projects_by_activity(
    pool: Pool, days: int = 7, limit: int = 10
) -> list[dict[str, Any]]:
    """Most-active projects over the last `days` days, ranked by total requests,
    split into writes vs recalls, with the project name joined in."""
    rows = await pool.fetch(
        "SELECT u.tenant_id, p.name, "
        "COUNT(*) FILTER (WHERE u.endpoint = '/v1/memories') AS writes, "
        "COUNT(*) FILTER (WHERE u.endpoint = '/v1/recall') AS recalls, "
        "COUNT(*) AS total "
        "FROM usage_log u LEFT JOIN projects p ON p.tenant_id = u.tenant_id "
        "WHERE u.created_at >= NOW() - make_interval(days => $1) "
        "GROUP BY u.tenant_id, p.name ORDER BY total DESC LIMIT $2",
        days,
        limit,
    )
    return [dict(row) for row in rows]


async def project_sources(pool: Pool, tenant_id: str) -> list[dict[str, Any]]:
    """Per-source write breakdown for one project: which sources (agents) wrote,
    how many writes each, and when each last wrote. The multi-agent provenance
    view -- 'which of my agents is doing what'."""
    rows = await pool.fetch(
        "SELECT source, COUNT(*) AS write_count, "
        "SUM(extracted_entity_count)::bigint AS entities, "
        "SUM(extracted_relation_count)::bigint AS relations, "
        "MAX(created_at) AS last_activity_at "
        "FROM memory_writes WHERE tenant_id = $1 "
        "GROUP BY source ORDER BY write_count DESC",
        tenant_id,
    )
    return [dict(row) for row in rows]


# --- User-facing usage monitoring (tenant-scoped, current-billing-period) -----
#
# All scoped to one tenant_id. tokens_used is nullable on usage_log (writes made
# before token capture, or rows where no LLM call happened), so every SUM uses
# COALESCE(..., 0) -- a NULL contributes 0, never an error or a NULL total.


async def writes_since(pool: Pool, tenant_id: str, since: datetime) -> int:
    """Count of memory writes for a tenant since `since` (inclusive)."""
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS n FROM memory_writes WHERE tenant_id = $1 AND created_at >= $2",
        tenant_id,
        since,
    )
    assert row is not None
    return int(row["n"])


async def usage_totals_since(pool: Pool, tenant_id: str, since: datetime) -> dict[str, int]:
    """Recall count and total tokens for a tenant since `since`. NULL tokens
    count as 0 (COALESCE), so a tenant with un-tokened rows still totals cleanly."""
    row = await pool.fetchrow(
        "SELECT COUNT(*) FILTER (WHERE endpoint = '/v1/recall') AS recalls, "
        "COALESCE(SUM(tokens_used), 0)::bigint AS tokens "
        "FROM usage_log WHERE tenant_id = $1 AND created_at >= $2",
        tenant_id,
        since,
    )
    assert row is not None
    return {"recalls": int(row["recalls"]), "tokens": int(row["tokens"])}


async def usage_by_endpoint_since(
    pool: Pool, tenant_id: str, since: datetime
) -> list[dict[str, Any]]:
    """Per-endpoint call count and token sum for a tenant since `since`."""
    rows = await pool.fetch(
        "SELECT endpoint, COUNT(*) AS calls, COALESCE(SUM(tokens_used), 0)::bigint AS tokens "
        "FROM usage_log WHERE tenant_id = $1 AND created_at >= $2 "
        "GROUP BY endpoint",
        tenant_id,
        since,
    )
    return [dict(row) for row in rows]


async def usage_log_by_day(pool: Pool, tenant_id: str, days: int = 30) -> list[dict[str, Any]]:
    """Daily recall count and token sum for a tenant over the last `days` days.
    (Writes-per-day come from writes_over_time; the route merges the two.)"""
    rows = await pool.fetch(
        "SELECT date_trunc('day', created_at)::date AS day, "
        "COUNT(*) FILTER (WHERE endpoint = '/v1/recall') AS recalls, "
        "COALESCE(SUM(tokens_used), 0)::bigint AS tokens "
        "FROM usage_log WHERE tenant_id = $1 "
        "AND created_at >= NOW() - make_interval(days => $2) "
        "GROUP BY day ORDER BY day",
        tenant_id,
        days,
    )
    return [dict(row) for row in rows]


async def delete_project_cascade(pool: Pool, tenant_id: str) -> bool:
    """Wipe all Postgres rows for a tenant, in FK-safe order, in one
    transaction: usage_log -> agents -> api_keys -> memory_writes -> project.
    Returns True if the project existed (and was therefore deleted).

    This is the Postgres half of the admin "wipe tenant" operation; the caller
    is responsible for dropping the tenant's FalkorDB graph separately. Order
    matters: usage_log references api_keys, and api_keys/memory_writes reference
    projects, so dependents are removed before the rows they point at."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM usage_log WHERE tenant_id = $1", tenant_id)
            await conn.execute("DELETE FROM agents WHERE tenant_id = $1", tenant_id)
            await conn.execute("DELETE FROM api_keys WHERE tenant_id = $1", tenant_id)
            await conn.execute("DELETE FROM memory_writes WHERE tenant_id = $1", tenant_id)
            result = await conn.execute("DELETE FROM projects WHERE tenant_id = $1", tenant_id)
    return _command_succeeded(result)


async def get_api_key_owner(pool: Pool, key_id: UUID) -> dict[str, Any] | None:
    """Minimal metadata for any key by id, regardless of owner (admin lookup)."""
    row = await pool.fetchrow(
        "SELECT id, tenant_id, user_id, name, revoked_at FROM api_keys WHERE id = $1",
        key_id,
    )
    return dict(row) if row else None
