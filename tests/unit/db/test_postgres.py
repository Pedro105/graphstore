"""Unit tests for the Postgres auth helpers, asyncpg fully mocked.

Covers API-key resolution (valid / invalid / revoked), key generation and
hashing, usage logging never raising, and the create/revoke command-tag
parsing -- none of which touch a real database.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from contextstore.db import postgres


def _key_row(api_key_id, tenant_id, raw_key):
    """A fake api_keys row as asyncpg would return it (mapping access by key)."""
    return {"id": api_key_id, "tenant_id": tenant_id, "key_hash": postgres.hash_key(raw_key)}


def test_generate_api_key_has_prefix_and_entropy():
    key = postgres.generate_api_key()
    assert key.startswith(postgres.KEY_PREFIX)
    assert len(key) > len(postgres.KEY_PREFIX) + 20
    assert postgres.generate_api_key() != postgres.generate_api_key()


def test_hash_and_verify_roundtrip():
    raw = postgres.generate_api_key()
    hashed = postgres.hash_key(raw)
    assert hashed != raw
    assert postgres._verify_key(raw, hashed) is True
    assert postgres._verify_key("csk_live_wrong", hashed) is False
    # A malformed stored hash is a non-match, not a crash.
    assert postgres._verify_key(raw, "not-a-bcrypt-hash") is False


async def test_resolve_valid_key_returns_tenant_and_touches_last_used():
    raw = postgres.generate_api_key()
    key_id = uuid4()
    pool = AsyncMock()
    pool.fetch.return_value = [_key_row(key_id, "acme", raw)]

    resolved = await postgres.resolve_api_key(pool, raw)

    assert resolved is not None
    assert resolved.tenant_id == "acme"
    assert resolved.api_key_id == key_id
    # last_used_at is updated on a successful match.
    pool.execute.assert_awaited_once()
    assert "last_used_at" in pool.execute.await_args.args[0]

    # The convenience wrapper returns just the tenant.
    assert await postgres.get_tenant_id_for_key(pool, raw) == "acme"


async def test_resolve_invalid_key_returns_none():
    pool = AsyncMock()
    # An active key exists, but for a different raw value.
    pool.fetch.return_value = [_key_row(uuid4(), "acme", postgres.generate_api_key())]

    assert await postgres.resolve_api_key(pool, "csk_live_does_not_match") is None
    assert await postgres.get_tenant_id_for_key(pool, "csk_live_does_not_match") is None
    # No match -> last_used_at not touched.
    pool.execute.assert_not_awaited()


async def test_resolve_revoked_key_returns_none():
    # Revocation is enforced by the query's `WHERE revoked_at IS NULL`, so a
    # revoked key simply isn't among the rows fetched -> no candidate matches.
    pool = AsyncMock()
    pool.fetch.return_value = []

    assert await postgres.resolve_api_key(pool, postgres.generate_api_key()) is None
    assert "revoked_at IS NULL" in pool.fetch.await_args.args[0]


async def test_log_usage_never_raises():
    pool = AsyncMock()
    pool.execute.side_effect = RuntimeError("db down")

    # Must swallow the error -- usage accounting can't be allowed to fail a request.
    await postgres.log_usage(pool, uuid4(), "acme", "/v1/recall", tokens_used=None)


async def test_create_api_key_returns_raw_key_and_stores_hash():
    new_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow.return_value = {"id": new_id}

    raw_key, api_key_id = await postgres.create_api_key(pool, uuid4(), "acme", "dev")

    assert raw_key.startswith(postgres.KEY_PREFIX)
    assert api_key_id == new_id
    # The plaintext key is never passed to the INSERT -- only its hash.
    insert_args = pool.fetchrow.await_args.args
    assert raw_key not in insert_args
    stored_hash = insert_args[3]
    assert postgres._verify_key(raw_key, stored_hash) is True


async def test_revoke_api_key_parses_command_tag():
    pool = AsyncMock()
    pool.execute.return_value = "UPDATE 1"
    assert await postgres.revoke_api_key(pool, uuid4()) is True

    pool.execute.return_value = "UPDATE 0"
    assert await postgres.revoke_api_key(pool, uuid4()) is False


async def test_list_api_keys_returns_safe_fields_scoped_to_tenant():
    pool = AsyncMock()
    pool.fetch.return_value = [
        {
            "id": uuid4(),
            "name": "dev",
            "created_at": "t0",
            "last_used_at": None,
            "revoked_at": None,
        }
    ]

    keys = await postgres.list_api_keys(pool, "acme")

    assert keys[0]["name"] == "dev"
    # Never selects the hash/raw key, and filters by tenant.
    query = pool.fetch.await_args.args[0]
    assert "key_hash" not in query
    assert "WHERE tenant_id = $1" in query
    assert pool.fetch.await_args.args[1] == "acme"


async def test_revoke_api_key_for_tenant_constrains_to_owner():
    pool = AsyncMock()
    pool.execute.return_value = "UPDATE 1"
    tenant_id = "acme"
    assert await postgres.revoke_api_key_for_tenant(pool, uuid4(), tenant_id) is True
    query = pool.execute.await_args.args[0]
    assert "tenant_id = $2" in query  # ownership constraint in the WHERE clause

    pool.execute.return_value = "UPDATE 0"  # not owned / not found
    assert await postgres.revoke_api_key_for_tenant(pool, uuid4(), tenant_id) is False


async def test_create_agent_returns_row_scoped_to_tenant():
    new_id = uuid4()
    pool = AsyncMock()
    pool.fetchrow.return_value = {
        "id": new_id,
        "name": "CRM Agent",
        "description": "syncs CRM",
        "created_at": "t0",
    }

    agent = await postgres.create_agent(pool, "acme", "CRM Agent", "syncs CRM")

    assert agent["id"] == new_id
    assert pool.fetchrow.await_args.args[1] == "acme"  # tenant_id bound first


async def test_list_and_delete_agents_are_tenant_scoped():
    pool = AsyncMock()
    pool.fetch.return_value = [
        {"id": uuid4(), "name": "a", "description": None, "created_at": "t0"}
    ]
    agents = await postgres.list_agents(pool, "acme")
    assert len(agents) == 1
    assert "WHERE tenant_id = $1" in pool.fetch.await_args.args[0]

    pool.execute.return_value = "DELETE 1"
    assert await postgres.delete_agent(pool, "acme", uuid4()) is True
    delete_query = pool.execute.await_args.args[0]
    assert "tenant_id = $2" in delete_query

    pool.execute.return_value = "DELETE 0"
    assert await postgres.delete_agent(pool, "acme", uuid4()) is False
