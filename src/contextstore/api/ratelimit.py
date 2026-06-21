"""In-process per-API-key rate limiting.

A sliding-window counter keyed on `api_key_id` (the API-product-correct key --
IP-based limiting would punish many agents sharing an egress and reward a
single agent rotating IPs). In-process is sufficient for the current
single-instance deployment; a multi-instance deployment would move this to a
shared store (e.g. Redis) keyed the same way.

The limiter is enforced as a FastAPI dependency rather than Starlette
middleware on purpose: the rate-limit key is `api_key_id`, which is only known
after the auth dependency has resolved the key against Postgres. A pre-handler
middleware would have to repeat that lookup; a dependency that depends on
`require_api_key` reuses it.
"""

import math
import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock

from fastapi import Depends, HTTPException, status

from contextstore.api.auth import AuthContext, require_api_key
from contextstore.core.config import get_settings


class SlidingWindowRateLimiter:
    """Fixed-duration sliding window. `check` records a hit and reports whether
    it was within `limit` for the trailing `window_seconds`.

    `clock` is injectable so tests can advance time deterministically instead of
    sleeping.
    """

    def __init__(
        self, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds). When not allowed,
        retry_after is the time until the oldest hit in the window expires."""
        now = self._clock()
        cutoff = now - self._window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = self._window - (now - hits[0])
                return False, max(retry_after, 0.0)
            hits.append(now)
            return True, 0.0


# Process-wide limiter shared across requests.
_limiter = SlidingWindowRateLimiter()


class FailedAttemptLimiter:
    """Locks a key out after too many failures in a sliding window.

    Unlike SlidingWindowRateLimiter (which counts *all* requests), this counts
    only recorded *failures* -- a successful auth never touches it. Used to make
    the operator admin token (api/auth.require_admin) non-brute-forceable: once a
    source IP is locked, even a request bearing the correct token is refused,
    which also denies an attacker the timing signal of "right vs wrong token".

    Limits are passed per call rather than fixed at construction so they can be
    read from settings at request time (and so tests can be explicit/deterministic).
    `clock` is injectable for deterministic tests.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, hits: deque[float], window_seconds: float) -> None:
        cutoff = self._clock() - window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def is_locked(self, key: str, max_attempts: int, window_seconds: float) -> tuple[bool, float]:
        """Whether `key` is currently locked out, and for how many more seconds.

        Read-only: does not record anything (so checking the lock can't itself
        trip it). Locked when the count of non-expired failures has reached
        `max_attempts`."""
        with self._lock:
            hits = self._failures[key]
            self._prune(hits, window_seconds)
            if len(hits) >= max_attempts:
                retry_after = window_seconds - (self._clock() - hits[0])
                return True, max(retry_after, 0.0)
            return False, 0.0

    def record_failure(self, key: str, window_seconds: float) -> None:
        """Record one failed attempt for `key`."""
        with self._lock:
            hits = self._failures[key]
            self._prune(hits, window_seconds)
            hits.append(self._clock())


# Process-wide failed-admin-auth limiter, keyed by source IP.
_admin_failed_limiter = FailedAttemptLimiter()


def rate_limited(endpoint: str, limit_getter: Callable[[], int]) -> Callable[..., object]:
    """Build a dependency that enforces this endpoint's per-key limit, then
    returns the AuthContext so the route still receives it. `limit_getter` reads
    the limit at request time so env-configured limits apply without a restart.
    """

    async def dependency(auth: AuthContext = Depends(require_api_key)) -> AuthContext:
        allowed, retry_after = _limiter.check(f"{auth.api_key_id}:{endpoint}", limit_getter())
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(int(math.ceil(retry_after)))},
            )
        return auth

    return dependency


require_recall_quota = rate_limited("/v1/recall", lambda: get_settings().rate_limit_recall)
require_memories_quota = rate_limited("/v1/memories", lambda: get_settings().rate_limit_memories)
