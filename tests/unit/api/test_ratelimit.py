"""Unit tests for the sliding-window rate limiter and its dependency wrapper."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from contextstore.api import ratelimit
from contextstore.api.auth import AuthContext
from contextstore.api.ratelimit import SlidingWindowRateLimiter, rate_limited


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_allows_up_to_limit_then_blocks():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(window_seconds=60.0, clock=clock)

    assert limiter.check("k", 2)[0] is True
    assert limiter.check("k", 2)[0] is True

    allowed, retry_after = limiter.check("k", 2)
    assert allowed is False
    assert retry_after > 0  # time until the oldest hit ages out


def test_window_resets_after_it_elapses():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(window_seconds=60.0, clock=clock)

    assert limiter.check("k", 1)[0] is True
    assert limiter.check("k", 1)[0] is False  # over limit within the window

    clock.t = 61.0  # advance past the window
    assert limiter.check("k", 1)[0] is True  # oldest hit expired -> allowed again


def test_limits_are_per_key():
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(window_seconds=60.0, clock=clock)

    assert limiter.check("key_a", 1)[0] is True
    assert limiter.check("key_a", 1)[0] is False
    # A different key has its own independent budget.
    assert limiter.check("key_b", 1)[0] is True


async def test_dependency_raises_429_with_retry_after(monkeypatch):
    # Isolate from the process-wide limiter so other tests don't interfere.
    monkeypatch.setattr(ratelimit, "_limiter", SlidingWindowRateLimiter(window_seconds=60.0))
    dependency = rate_limited("/v1/recall", lambda: 1)
    auth = AuthContext(tenant_id="acme", api_key_id=uuid4(), user_id=uuid4())

    # First call is within the limit and returns the AuthContext untouched.
    assert await dependency(auth=auth) is auth

    with pytest.raises(HTTPException) as exc:
        await dependency(auth=auth)
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers
