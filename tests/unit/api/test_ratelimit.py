"""Unit tests for the sliding-window rate limiter and its dependency wrapper."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from contextstore.api import ratelimit
from contextstore.api.auth import AuthContext
from contextstore.api.ratelimit import (
    FailedAttemptLimiter,
    SlidingWindowRateLimiter,
    rate_limited,
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


# --- FailedAttemptLimiter (admin brute-force lock) ---------------------------

ATTEMPTS = 5
WINDOW = 900.0


def test_n_failures_trigger_lockout():
    clock = FakeClock()
    limiter = FailedAttemptLimiter(clock=clock)
    # Below the threshold: not locked.
    for _ in range(ATTEMPTS - 1):
        limiter.record_failure("ip1", WINDOW)
    assert limiter.is_locked("ip1", ATTEMPTS, WINDOW)[0] is False
    # The Nth failure trips the lock.
    limiter.record_failure("ip1", WINDOW)
    locked, retry_after = limiter.is_locked("ip1", ATTEMPTS, WINDOW)
    assert locked is True
    assert 0 < retry_after <= WINDOW


def test_lockout_resets_after_window():
    clock = FakeClock()
    limiter = FailedAttemptLimiter(clock=clock)
    for _ in range(ATTEMPTS):
        limiter.record_failure("ip1", WINDOW)
    assert limiter.is_locked("ip1", ATTEMPTS, WINDOW)[0] is True
    # Advance past the window: the old failures expire, the lock clears.
    clock.t += WINDOW + 1
    assert limiter.is_locked("ip1", ATTEMPTS, WINDOW)[0] is False


def test_successful_auth_does_not_count():
    # The limiter only ever sees failures (record_failure); a success records
    # nothing, so an IP that never fails is never locked.
    limiter = FailedAttemptLimiter(clock=FakeClock())
    for _ in range(ATTEMPTS * 3):
        assert limiter.is_locked("ip-clean", ATTEMPTS, WINDOW)[0] is False


def test_different_ips_have_independent_limits():
    clock = FakeClock()
    limiter = FailedAttemptLimiter(clock=clock)
    for _ in range(ATTEMPTS):
        limiter.record_failure("ip-bad", WINDOW)
    assert limiter.is_locked("ip-bad", ATTEMPTS, WINDOW)[0] is True
    # A different IP is unaffected.
    assert limiter.is_locked("ip-good", ATTEMPTS, WINDOW)[0] is False


def test_is_locked_is_read_only():
    # Checking the lock must not itself record an attempt (no self-tripping).
    limiter = FailedAttemptLimiter(clock=FakeClock())
    for _ in range(100):
        limiter.is_locked("ip1", ATTEMPTS, WINDOW)
    assert limiter.is_locked("ip1", ATTEMPTS, WINDOW)[0] is False


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
