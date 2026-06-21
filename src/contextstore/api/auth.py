"""API-key authentication and the admin-token guard.

Every `/v1/` data route depends on `require_api_key`, which resolves the
`Authorization: Bearer <key>` header to an identity (user + the key's bound
tenant) via Postgres. The tenant is *never* taken from a request body, and the
key proves the user -- this is what makes tenant isolation enforceable rather
than advisory (see docs/decisions/0002-graph-per-tenant-isolation.md).

Multi-project access: a request may target one of the authenticated user's
*other* projects via an `X-Project: <tenant_id>` header (the dashboard's
workspace switcher uses this). This is NOT a softening of isolation -- the
header is not a secret and is never trusted on its own. `require_api_key`
verifies, server-side and on every request, that the calling user *owns* the
named project before overriding the tenant for that request; a non-owner (or a
nonexistent project) fails closed with 403 and never falls back to anything.
The boundary is identical to before: the key proves the user, and the user must
own whatever project the request acts on.

The operator-only `/v1/keys` endpoints use `require_admin` (a shared admin
token) instead, since they mint/revoke the very keys the data routes check.
The `/v1/admin/*` namespace likewise uses `require_admin`, so X-Project never
applies there.
"""

import math
import secrets
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from contextstore.core.config import get_settings
from contextstore.db import postgres
from contextstore.db.postgres import Pool

logger = structlog.get_logger()

_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def _client_ip(request: Request) -> str:
    """Best-effort source IP for the admin brute-force limiter. Behind Fly's
    proxy the real client is the first hop in X-Forwarded-For; fall back to the
    direct peer for local/un-proxied runs."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class AuthContext(BaseModel):
    """The authenticated identity a route handler builds its Scope from."""

    tenant_id: str
    api_key_id: UUID
    user_id: UUID


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


# Shared by every route that needs the auth Postgres pool (data routes,
# key/project management, and the admin namespace).
DbDep = Annotated[Pool, Depends(get_db)]


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
    x_project: str | None = Header(default=None, alias="X-Project"),
    db: Pool = Depends(get_db),
) -> AuthContext:
    """Resolve the Bearer API key to an AuthContext, or 401 if missing,
    malformed, invalid, or revoked.

    If an `X-Project` header is present and names a project other than the key's
    own tenant, the calling user's ownership of it is verified here -- once, on
    this request, with no cached result -- and the tenant is overridden only on
    success. A project the user does not own (or one that does not exist) is
    rejected with 403; the request never falls back to the key's tenant. This
    runs at the auth layer so it applies uniformly to every data route, and the
    same 403 is returned whether the project is unowned or absent, so the
    response never reveals whether a given project id exists.
    """
    token = _bearer_token(authorization)
    resolved = await postgres.resolve_api_key(db, token)
    if resolved is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
            headers=_BEARER_CHALLENGE,
        )

    tenant_id = resolved.tenant_id
    # Project override: only when the header names a *different* project than the
    # key's own tenant (selecting your own tenant needs no extra check -- the key
    # already proves it). Ownership is the entire boundary; fail closed on miss.
    if x_project is not None and x_project != resolved.tenant_id:
        project = await postgres.get_project_for_user(db, x_project, resolved.user_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Project not found or not owned by the authenticated user.",
            )
        tenant_id = x_project

    return AuthContext(
        tenant_id=tenant_id,
        api_key_id=resolved.api_key_id,
        user_id=resolved.user_id,
    )


def require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Guard the operator-only endpoints with the shared ADMIN_TOKEN.

    Constant-time comparison so the token isn't discoverable by timing, plus an
    in-process per-IP brute-force lock: after `admin_rate_limit_attempts` failed
    attempts within the window, the source IP is locked out (429) and every
    further request is refused *regardless of whether its token is correct* --
    this denies both brute-forcing and the timing signal of a right-vs-wrong
    token. Every failed attempt is logged at WARNING (the audit trail). 503 if no
    admin token is configured (endpoints are then closed)."""
    settings = get_settings()
    if settings.admin_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Key management is not configured (ADMIN_TOKEN unset).",
        )

    # Lazy import: ratelimit imports this module, so importing it at module load
    # would be circular.
    from contextstore.api.ratelimit import _admin_failed_limiter

    source_ip = _client_ip(request)
    attempts = settings.admin_rate_limit_attempts
    window = settings.admin_rate_limit_window_seconds

    # Lock check runs BEFORE the token check, so a locked IP is refused even when
    # the token happens to be correct (no timing oracle).
    locked, retry_after = _admin_failed_limiter.is_locked(source_ip, attempts, window)
    if locked:
        logger.warning("admin_auth.locked_out", source_ip=source_ip, retry_after=retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed admin authentication attempts. Try again later.",
            headers={"Retry-After": str(math.ceil(retry_after))},
        )

    try:
        token = _bearer_token(authorization)
        valid = secrets.compare_digest(token, settings.admin_token.get_secret_value())
    except HTTPException:
        # A missing/malformed header is itself a failed attempt.
        valid = False

    if not valid:
        _admin_failed_limiter.record_failure(source_ip, window)
        logger.warning("admin_auth.failed", source_ip=source_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token.",
            headers=_BEARER_CHALLENGE,
        )
