"""Redis-backed rate limiter for anti-macro protection.

Replaces the in-memory RateLimiter for multi-process (gunicorn) deployments.
All state is stored in Redis so every worker process shares the same counters.

Defense strategies (same as in-memory version):
1. Sliding window: max N requests per window using a Redis sorted set
2. Minimum interval: enforce delay between consecutive requests using a Redis key with TTL
3. Failure penalty: temporarily block after too many consecutive failures using Redis INCR + TTL
"""

import time

import redis.asyncio as aioredis


class RedisRateLimiter:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_requests: int = 5,
        window_seconds: float = 10.0,
        min_interval_seconds: float = 1.0,
        max_failures: int = 10,
        block_duration_seconds: float = 30.0,
        key_prefix: str = "rl",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.min_interval_seconds = min_interval_seconds
        self.max_failures = max_failures
        self.block_duration_seconds = block_duration_seconds
        self.key_prefix = key_prefix
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    # ── key helpers ──────────────────────────────────────────────────────────

    def _window_key(self, key) -> str:
        return f"{self.key_prefix}:window:{key}"

    def _interval_key(self, key) -> str:
        return f"{self.key_prefix}:interval:{key}"

    def _failures_key(self, key) -> str:
        return f"{self.key_prefix}:failures:{key}"

    def _block_key(self, key) -> str:
        return f"{self.key_prefix}:block:{key}"

    # ── public interface ─────────────────────────────────────────────────────

    async def check(self, key) -> tuple[bool, str]:
        """Check whether a request from *key* is allowed.

        Returns:
            (allowed, reason) — allowed is True if request can proceed.
        """
        now = time.time()

        # 1. Failure block
        if await self._redis.exists(self._block_key(key)):
            ttl = await self._redis.ttl(self._block_key(key))
            return False, f"Too many failed attempts. Try again in {ttl}s"

        # 2. Minimum interval (last-request key still alive → too fast)
        if self.min_interval_seconds > 0:
            if await self._redis.exists(self._interval_key(key)):
                return False, "Too fast. Please wait before retrying"

        # 3. Sliding window via sorted set
        window_key = self._window_key(key)
        cutoff = now - self.window_seconds

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(window_key, "-inf", cutoff)   # evict stale entries
        pipe.zcard(window_key)                               # current count
        pipe.zadd(window_key, {str(now): now})              # add this request
        pipe.expire(window_key, int(self.window_seconds) + 1)
        results = await pipe.execute()

        count_before_add = results[1]   # count BEFORE we added the new entry
        if count_before_add >= self.max_requests:
            # remove the entry we just added — request is rejected
            await self._redis.zrem(window_key, str(now))
            return (
                False,
                f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s",
            )

        # 4. Stamp the interval key so the next rapid request is blocked
        if self.min_interval_seconds > 0:
            await self._redis.set(
                self._interval_key(key),
                1,
                px=int(self.min_interval_seconds * 1000),
            )

        return True, ""

    async def record_failure(self, key) -> None:
        """Record a failed attempt. Triggers a block after max_failures."""
        failures_key = self._failures_key(key)
        count = await self._redis.incr(failures_key)
        # keep the failures key alive a bit longer than the block duration
        await self._redis.expire(failures_key, int(self.block_duration_seconds) + 60)
        if count >= self.max_failures:
            await self._redis.set(
                self._block_key(key),
                1,
                px=int(self.block_duration_seconds * 1000),
            )

    async def record_success(self, key) -> None:
        """Reset failure counter on success."""
        await self._redis.delete(self._failures_key(key))
