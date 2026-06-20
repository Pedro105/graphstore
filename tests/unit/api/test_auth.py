"""Unit tests for the auth dependencies, called as plain functions.

`require_api_key` / `require_admin` / `get_db` are exercised directly (no
TestClient) so the auth logic is tested in isolation; the asyncpg lookup is
stubbed via monkeypatch and a dummy Request stands in for FastAPI's.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from contextstore.api import auth
from contextstore.db.postgres import ResolvedKey


def _request_with_pool(pool):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))


def test_get_db_returns_pool_when_configured():
    pool = object()
    assert auth.get_db(_request_with_pool(pool)) is pool


def test_get_db_503_when_unconfigured():
    with pytest.raises(HTTPException) as exc:
        auth.get_db(_request_with_pool(None))
    assert exc.value.status_code == 503


async def test_require_api_key_valid(monkeypatch):
    key_id = uuid4()

    async def fake_resolve(db, token):
        assert token == "goodkey"
        return ResolvedKey(api_key_id=key_id, tenant_id="acme", user_id=uuid4())

    monkeypatch.setattr(auth.postgres, "resolve_api_key", fake_resolve)

    ctx = await auth.require_api_key(authorization="Bearer goodkey", db=object())
    assert ctx.tenant_id == "acme"
    assert ctx.api_key_id == key_id


async def test_require_api_key_missing_header_401():
    with pytest.raises(HTTPException) as exc:
        await auth.require_api_key(authorization=None, db=object())
    assert exc.value.status_code == 401


async def test_require_api_key_malformed_header_401():
    with pytest.raises(HTTPException) as exc:
        await auth.require_api_key(authorization="Token abc", db=object())
    assert exc.value.status_code == 401


async def test_require_api_key_invalid_key_401(monkeypatch):
    async def fake_resolve(db, token):
        return None

    monkeypatch.setattr(auth.postgres, "resolve_api_key", fake_resolve)

    with pytest.raises(HTTPException) as exc:
        await auth.require_api_key(authorization="Bearer badkey", db=object())
    assert exc.value.status_code == 401


def _settings_with_admin(token):
    return SimpleNamespace(admin_token=SecretStr(token) if token is not None else None)


def test_require_admin_valid(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings_with_admin("s3cret"))
    # Returns None (no raise) on a correct token.
    assert auth.require_admin(authorization="Bearer s3cret") is None


def test_require_admin_wrong_token_401(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings_with_admin("s3cret"))
    with pytest.raises(HTTPException) as exc:
        auth.require_admin(authorization="Bearer wrong")
    assert exc.value.status_code == 401


def test_require_admin_unconfigured_503(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings_with_admin(None))
    with pytest.raises(HTTPException) as exc:
        auth.require_admin(authorization="Bearer anything")
    assert exc.value.status_code == 503
