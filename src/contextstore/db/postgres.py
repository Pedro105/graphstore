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
    """A successfully authenticated API key: which key, and the tenant it
    grants access to. tenant_id is authoritative -- it comes from Postgres, not
    from the caller."""

    api_key_id: UUID
    tenant_id: str


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
    rows = await pool.fetch("SELECT id, tenant_id, key_hash FROM api_keys WHERE revoked_at IS NULL")
    for row in rows:
        if _verify_key(raw_key, row["key_hash"]):
            await pool.execute("UPDATE api_keys SET last_used_at = NOW() WHERE id = $1", row["id"])
            return ResolvedKey(api_key_id=row["id"], tenant_id=row["tenant_id"])
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
) -> None:
    """Fire-and-forget usage record. Never raises -- usage accounting must not
    be able to fail a request."""
    try:
        await pool.execute(
            "INSERT INTO usage_log (api_key_id, tenant_id, endpoint, tokens_used) "
            "VALUES ($1, $2, $3, $4)",
            api_key_id,
            tenant_id,
            endpoint,
            tokens_used,
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


async def list_agents(pool: Pool, tenant_id: str) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        "SELECT id, name, description, created_at FROM agents "
        "WHERE tenant_id = $1 ORDER BY created_at",
        tenant_id,
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
