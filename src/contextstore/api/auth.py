"""API-key authentication and the admin-token guard.

Every `/v1/` data route depends on `require_api_key`, which resolves the
`Authorization: Bearer <key>` header to a tenant via Postgres. tenant_id is
*never* read from the request body -- it is authoritative from the key lookup,
which is what makes tenant isolation enforceable rather than advisory (see
docs/decisions/0002-graph-per-tenant-isolation.md).

The operator-only `/v1/keys` endpoints use `require_admin` (a shared admin
token) instead, since they mint/revoke the very keys the data routes check.
"""

import secrets
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from contextstore.core.config import get_settings
from contextstore.db import postgres
from contextstore.db.postgres import Pool

_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


class AuthContext(BaseModel):
    """The authenticated identity a route handler builds its Scope from."""

    tenant_id: str
    api_key_id: UUID


def get_db(request: Request) -> Pool:
    """The asyncpg pool from app.state, or 503 if auth is unconfigured (no
    DATABASE_URL). Refusing the request is the safe default -- without the pool
    we can't resolve a tenant, and silently proceeding would be the very
    spoofing hole this work closes."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication backend is not configured (DATABASE_URL unset).",
        )
    return pool


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers=_BEARER_CHALLENGE,
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header; expected 'Bearer <key>'.",
            headers=_BEARER_CHALLENGE,
        )
    return token.strip()


async def require_api_key(
    authorization: str | None = Header(default=None),
    db: Pool = Depends(get_db),
) -> AuthContext:
    """Resolve the Bearer API key to an AuthContext, or 401 if missing,
    malformed, invalid, or revoked."""
    token = _bearer_token(authorization)
    resolved = await postgres.resolve_api_key(db, token)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
            headers=_BEARER_CHALLENGE,
        )
    return AuthContext(tenant_id=resolved.tenant_id, api_key_id=resolved.api_key_id)


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """Guard the operator-only key-management endpoints with the shared
    ADMIN_TOKEN. Constant-time comparison so the token isn't discoverable by
    timing. 503 if no admin token is configured (endpoints are then closed)."""
    settings = get_settings()
    if settings.admin_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Key management is not configured (ADMIN_TOKEN unset).",
        )
    token = _bearer_token(authorization)
    if not secrets.compare_digest(token, settings.admin_token.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
            headers=_BEARER_CHALLENGE,
        )
