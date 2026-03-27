"""Rate limiter singleton for anti-macro protection.

Uses RedisRateLimiter for multi-process (gunicorn) compatibility.
All state is stored in Redis so every worker shares the same counters.
"""

from app.config import settings
from app.redis_rate_limiter import RedisRateLimiter

enrollment_rate_limiter = RedisRateLimiter(
    redis_url=settings.REDIS_URL,
    max_requests=5,
    window_seconds=10.0,
    min_interval_seconds=1.0,
    max_failures=10,
    block_duration_seconds=30.0,
    key_prefix="rl:enrollment",
)
