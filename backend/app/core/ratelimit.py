"""Optional per-client rate limiting for tool invocations.

First-principles goal: an unauthenticated tool site is one ``analyze_task``
call away from unbounded DeepSeek spend. This module caps invoke traffic per
client IP so a runaway client (or a script) cannot drain the server's API key.

Design:
- Fixed-window counter, ``limit`` requests per 60 seconds per IP.
- Redis-backed when Redis is reachable (multi-instance safe, atomic INCR).
- Falls back to an in-process counter otherwise (single instance).
- Disabled entirely unless ``RATE_LIMIT_ENABLED=true`` (the default).

The limiter never raises: if the backing store fails we log and allow the
request through rather than taking the API down.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque

from app.core.config import settings
from app.services.cache import get_redis

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60
# key -> deque of recent timestamps (in-memory fallback)
_memory: dict[str, deque[float]] = defaultdict(deque)
_memory_lock = asyncio.Lock()
# None = unknown, True/False = redis reachable last time
_redis_ok: bool | None = None


async def _allow_via_redis(key: str, limit: int) -> bool:
    r = await get_redis()
    redis_key = f"rl:{key}"
    pipe = r.pipeline()
    pipe.incr(redis_key)
    pipe.expire(redis_key, _WINDOW_SECONDS, nx=True)
    values = await pipe.execute()
    return int(values[0]) <= limit


async def _allow_via_memory(key: str, limit: int) -> bool:
    now = time.monotonic()
    async with _memory_lock:
        dq = _memory[key]
        while dq and now - dq[0] >= _WINDOW_SECONDS:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


async def is_allowed(client_ip: str) -> bool:
    """Return True if a request from ``client_ip`` may proceed."""
    if not settings.rate_limit_enabled:
        return True

    key = f"{client_ip}:invoke"
    limit = max(settings.rate_limit_per_minute, 1)

    global _redis_ok
    if _redis_ok is not False:
        try:
            allowed = await _allow_via_redis(key, limit)
            _redis_ok = True
            return allowed
        except Exception as exc:
            _redis_ok = False
            logger.warning(
                "Rate limiter: Redis unavailable, falling back to in-memory: %s", exc
            )

    return await _allow_via_memory(key, limit)
