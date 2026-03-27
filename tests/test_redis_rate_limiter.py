"""Tests for the Redis-backed rate limiter.

All tests run against a real Redis instance (localhost:6379).
Keys are namespaced with a unique prefix per test to avoid collisions.
"""

import asyncio
import time

import pytest

from app.redis_rate_limiter import RedisRateLimiter


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def make_limiter(**kwargs) -> RedisRateLimiter:
    """Create a RedisRateLimiter with a unique key prefix so each test is isolated."""
    prefix = f"test:{time.time_ns()}"
    defaults = dict(
        redis_url="redis://localhost:6379",
        max_requests=5,
        window_seconds=10.0,
        min_interval_seconds=0.0,
        max_failures=10,
        block_duration_seconds=30.0,
        key_prefix=prefix,
    )
    defaults.update(kwargs)
    return RedisRateLimiter(**defaults)


# ──────────────────────────────────────────────
# Basic allow / block
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_allows_normal_requests():
    """Normal requests within rate limit should pass."""
    limiter = make_limiter(max_requests=5, min_interval_seconds=0)
    for _ in range(5):
        allowed, reason = await limiter.check(1)
        assert allowed, reason


@pytest.mark.asyncio
async def test_blocks_after_rate_limit():
    """Requests exceeding rate limit should be rejected."""
    limiter = make_limiter(max_requests=3, min_interval_seconds=0)

    for _ in range(3):
        allowed, _ = await limiter.check(1)
        assert allowed

    allowed, reason = await limiter.check(1)
    assert not allowed
    assert "Rate limit exceeded" in reason


@pytest.mark.asyncio
async def test_independent_per_student():
    """Rate limiting should be independent per student ID."""
    limiter = make_limiter(max_requests=2, min_interval_seconds=0)

    # student 1 exhausts limit
    await limiter.check(1)
    await limiter.check(1)
    allowed, _ = await limiter.check(1)
    assert not allowed

    # student 2 is unaffected
    allowed, _ = await limiter.check(2)
    assert allowed


# ──────────────────────────────────────────────
# Minimum interval
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_min_interval_blocks_rapid_requests():
    """Requests faster than min_interval should be rejected."""
    limiter = make_limiter(max_requests=100, min_interval_seconds=0.5)

    allowed, _ = await limiter.check(1)
    assert allowed

    # immediate second request blocked
    allowed, reason = await limiter.check(1)
    assert not allowed
    assert "Too fast" in reason


@pytest.mark.asyncio
async def test_min_interval_allows_after_wait():
    """Request should be allowed after min_interval has passed."""
    limiter = make_limiter(max_requests=100, min_interval_seconds=0.3)

    await limiter.check(1)
    await asyncio.sleep(0.4)

    allowed, _ = await limiter.check(1)
    assert allowed


# ──────────────────────────────────────────────
# Sliding window expiry
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_window_expiry_resets_count():
    """Requests should be allowed again after the sliding window expires."""
    limiter = make_limiter(max_requests=2, window_seconds=0.5, min_interval_seconds=0)

    await limiter.check(1)
    await limiter.check(1)
    allowed, _ = await limiter.check(1)
    assert not allowed

    await asyncio.sleep(0.6)

    allowed, _ = await limiter.check(1)
    assert allowed


# ──────────────────────────────────────────────
# Failure penalty & block
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_failure_penalty_triggers_block():
    """Exceeding max_failures should temporarily block the key."""
    limiter = make_limiter(
        max_requests=100,
        min_interval_seconds=0,
        max_failures=3,
        block_duration_seconds=1.0,
    )

    for _ in range(3):
        await limiter.record_failure(1)

    allowed, reason = await limiter.check(1)
    assert not allowed
    assert "Too many failed attempts" in reason


@pytest.mark.asyncio
async def test_block_expires_after_duration():
    """Block should lift after block_duration_seconds."""
    limiter = make_limiter(
        max_requests=100,
        min_interval_seconds=0,
        max_failures=2,
        block_duration_seconds=0.5,
    )

    await limiter.record_failure(1)
    await limiter.record_failure(1)

    allowed, _ = await limiter.check(1)
    assert not allowed

    await asyncio.sleep(0.6)

    allowed, _ = await limiter.check(1)
    assert allowed


@pytest.mark.asyncio
async def test_success_resets_failure_count():
    """record_success should reset failure counter so block threshold resets."""
    limiter = make_limiter(
        max_requests=100,
        min_interval_seconds=0,
        max_failures=3,
        block_duration_seconds=30.0,
    )

    # 2 failures — not yet blocked
    await limiter.record_failure(1)
    await limiter.record_failure(1)

    # success resets
    await limiter.record_success(1)

    # 2 more failures should NOT trigger block (counter was reset to 0)
    await limiter.record_failure(1)
    await limiter.record_failure(1)

    allowed, _ = await limiter.check(1)
    assert allowed


# ──────────────────────────────────────────────
# Multi-process simulation (the key Redis advantage)
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shared_state_across_instances():
    """Two separate limiter instances sharing a Redis prefix should share state.

    This simulates two gunicorn workers: both connect to the same Redis,
    so rate-limit counts are shared — unlike the in-memory limiter.
    """
    prefix = f"shared:{time.time_ns()}"
    kwargs = dict(
        redis_url="redis://localhost:6379",
        max_requests=3,
        window_seconds=10.0,
        min_interval_seconds=0.0,
        max_failures=10,
        block_duration_seconds=30.0,
        key_prefix=prefix,
    )

    worker1 = RedisRateLimiter(**kwargs)
    worker2 = RedisRateLimiter(**kwargs)

    # worker1 exhausts the limit
    await worker1.check(1)
    await worker1.check(1)
    await worker1.check(1)

    # worker2 (same Redis prefix) sees the shared count → blocked
    allowed, reason = await worker2.check(1)
    assert not allowed, "worker2 should see the shared rate-limit state from worker1"
    assert "Rate limit exceeded" in reason
