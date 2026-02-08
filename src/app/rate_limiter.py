"""In-memory rate limiter for anti-macro protection.

Tracks per-student request timestamps using a sliding window.
Designed for single-process deployment. For multi-process (gunicorn),
use Redis-backed rate limiting instead.

Defense strategies:
1. Rate limit: max N requests per window (e.g., 5 requests per 10 seconds)
2. Minimum interval: enforce delay between consecutive requests (e.g., 1 second)
3. Failure penalty: temporarily block after too many consecutive failures
"""

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(
        self,
        max_requests: int = 5,
        window_seconds: float = 10.0,
        min_interval_seconds: float = 1.0,
        max_failures: int = 10,
        block_duration_seconds: float = 30.0,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.min_interval_seconds = min_interval_seconds
        self.max_failures = max_failures
        self.block_duration_seconds = block_duration_seconds

        # student_id -> list of request timestamps
        self._requests: dict[int, list[float]] = defaultdict(list)
        # student_id -> consecutive failure count
        self._failures: dict[int, int] = defaultdict(int)
        # student_id -> block expiry timestamp
        self._blocked_until: dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def check(self, student_id: int) -> tuple[bool, str]:
        """Check if a request from this student is allowed.

        Returns:
            (allowed, reason) — allowed is True if request can proceed,
            reason explains the rejection if not allowed.
        """
        now = time.monotonic()

        async with self._lock:
            # 1. Check if student is temporarily blocked
            if student_id in self._blocked_until:
                if now < self._blocked_until[student_id]:
                    remaining = int(self._blocked_until[student_id] - now)
                    return False, f"Too many failed attempts. Try again in {remaining}s"
                else:
                    del self._blocked_until[student_id]
                    self._failures[student_id] = 0

            # 2. Clean old timestamps outside the window
            timestamps = self._requests[student_id]
            cutoff = now - self.window_seconds
            self._requests[student_id] = [t for t in timestamps if t > cutoff]
            timestamps = self._requests[student_id]

            # 3. Check minimum interval between requests
            if timestamps and (now - timestamps[-1]) < self.min_interval_seconds:
                return False, "Too fast. Please wait before retrying"

            # 4. Check rate limit (sliding window)
            if len(timestamps) >= self.max_requests:
                return False, f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s"

            # 5. Record this request
            timestamps.append(now)
            return True, ""

    async def record_failure(self, student_id: int) -> None:
        """Record a failed attempt. May trigger a temporary block."""
        async with self._lock:
            self._failures[student_id] += 1
            if self._failures[student_id] >= self.max_failures:
                self._blocked_until[student_id] = time.monotonic() + self.block_duration_seconds

    async def record_success(self, student_id: int) -> None:
        """Reset failure count on success."""
        async with self._lock:
            self._failures[student_id] = 0


# Global singleton
enrollment_rate_limiter = RateLimiter(
    max_requests=5,
    window_seconds=10.0,
    min_interval_seconds=1.0,
    max_failures=10,
    block_duration_seconds=30.0,
)
