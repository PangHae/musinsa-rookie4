"""Tests for the anti-macro rate limiter."""

import asyncio

import pytest

from app.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_allows_normal_requests():
    """Normal requests within rate limit should pass."""
    limiter = RateLimiter(max_requests=5, window_seconds=10, min_interval_seconds=0)
    for _ in range(5):
        allowed, reason = await limiter.check(student_id=1)
        assert allowed, reason


@pytest.mark.asyncio
async def test_blocks_after_rate_limit():
    """Requests exceeding rate limit should be rejected."""
    limiter = RateLimiter(max_requests=3, window_seconds=10, min_interval_seconds=0)

    for _ in range(3):
        allowed, _ = await limiter.check(student_id=1)
        assert allowed

    # 4th request should be blocked
    allowed, reason = await limiter.check(student_id=1)
    assert not allowed
    assert "Rate limit exceeded" in reason


@pytest.mark.asyncio
async def test_min_interval_enforcement():
    """Requests faster than min_interval should be rejected."""
    limiter = RateLimiter(
        max_requests=100, window_seconds=10, min_interval_seconds=0.5
    )

    allowed, _ = await limiter.check(student_id=1)
    assert allowed

    # Immediate second request should be blocked
    allowed, reason = await limiter.check(student_id=1)
    assert not allowed
    assert "Too fast" in reason

    # After waiting, should be allowed
    await asyncio.sleep(0.6)
    allowed, _ = await limiter.check(student_id=1)
    assert allowed


@pytest.mark.asyncio
async def test_failure_penalty_blocks():
    """Too many consecutive failures should trigger a block."""
    limiter = RateLimiter(
        max_requests=100,
        window_seconds=10,
        min_interval_seconds=0,
        max_failures=3,
        block_duration_seconds=1.0,
    )

    # Record 3 failures
    for _ in range(3):
        await limiter.record_failure(student_id=1)

    # Should now be blocked
    allowed, reason = await limiter.check(student_id=1)
    assert not allowed
    assert "Too many failed attempts" in reason

    # After block expires, should be allowed
    await asyncio.sleep(1.1)
    allowed, _ = await limiter.check(student_id=1)
    assert allowed


@pytest.mark.asyncio
async def test_success_resets_failures():
    """A successful request should reset the failure counter."""
    limiter = RateLimiter(
        max_requests=100,
        window_seconds=10,
        min_interval_seconds=0,
        max_failures=3,
        block_duration_seconds=10.0,
    )

    # Record 2 failures (not enough to block)
    await limiter.record_failure(student_id=1)
    await limiter.record_failure(student_id=1)

    # Success resets counter
    await limiter.record_success(student_id=1)

    # 2 more failures should not trigger block (counter was reset)
    await limiter.record_failure(student_id=1)
    await limiter.record_failure(student_id=1)

    allowed, _ = await limiter.check(student_id=1)
    assert allowed


@pytest.mark.asyncio
async def test_independent_per_student():
    """Rate limiting should be independent per student."""
    limiter = RateLimiter(max_requests=2, window_seconds=10, min_interval_seconds=0)

    # Student 1 uses up their limit
    await limiter.check(student_id=1)
    await limiter.check(student_id=1)
    allowed, _ = await limiter.check(student_id=1)
    assert not allowed

    # Student 2 should still be allowed
    allowed, _ = await limiter.check(student_id=2)
    assert allowed


@pytest.mark.asyncio
async def test_window_expiry():
    """Requests should be allowed again after the window expires."""
    limiter = RateLimiter(
        max_requests=2, window_seconds=0.5, min_interval_seconds=0
    )

    await limiter.check(student_id=1)
    await limiter.check(student_id=1)
    allowed, _ = await limiter.check(student_id=1)
    assert not allowed

    # Wait for window to expire
    await asyncio.sleep(0.6)
    allowed, _ = await limiter.check(student_id=1)
    assert allowed
