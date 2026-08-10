"""Optional per-client and global rate limiting for tool invocations.

First-principles goal: an unauthenticated tool site is one ``analyze_task``
call away from unbounded DeepSeek spend. This module caps invoke traffic so a
runaway client (or a script) cannot drain the server's API key.

Design:
- Fixed-window counter, ``limit`` requests per 60 seconds.
- Two independent buckets are checked: per-client-IP and a global budget
  (``RATE_LIMIT_GLOBAL_PER_MINUTE``). The global bucket bounds worst-case
  spend even if clients rotate IPs or hide behind a shared proxy.
- Redis-backed when Redis is reachable (multi-instance safe, atomic INCR);
  falls back to an in-process counter otherwise (single instance).
- After a Redis failure the limiter uses the in-memory fallback for a
  cooldown window, then retries Redis — a transient blip does not permanently
  disable multi-instance-safe limiting.
- The in-memory store is pruned so idle keys cannot grow without bound.
- The limiter never raises: if the backing store fails we log and allow the
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
# Above this many tracked keys the in-memory fallback prunes idle entries.
_MEMORY_MAX_KEYS = 10_000
# Seconds to wait before probing Redis again after a failure.
_REDIS_RETRY_AFTER = 30

# key -> deque of recent timestamps (in-memory fallback)
_memory: dict[str, deque[float]] = defaultdict(deque)
_memory_lock = asyncio.Lock()
# None = unknown, True/False = redis reachable last time
_redis_ok: bool | None = None
# monotonic time until which we skip probing Redis after a failure
_redis_cooldown_until = 0.0


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
        if len(_memory) > _MEMORY_MAX_KEYS:
            # Prune back under budget: idle keys first (cheap), then the
            # least-recently-active keys. Evict only what is actually over
            # budget — a negative overflow after idle-eviction must not slice
            # from the end of the store, which keeps only the newest keys and
            # wipes nearly everything else.
            overflow = len(_memory) - _MEMORY_MAX_KEYS
            idle = [k for k in _memory if not _memory[k]]
            for k in idle[:overflow]:
                del _memory[k]
            overflow = len(_memory) - _MEMORY_MAX_KEYS
            if overflow > 0:
                # The leftmost deque entry is the oldest hit in the window, so
                # sort by it to evict the least-recently-active keys.
                by_age = sorted(
                    _memory.items(), key=lambda kv: kv[1][0] if kv[1] else 0.0
                )
                for k, _ in by_age[:overflow]:
                    del _memory[k]

        dq = _memory[key]
        while dq and now - dq[0] >= _WINDOW_SECONDS:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


async def _check(key: str, limit: int) -> bool:
    """Enforce one bucket: Redis if healthy, else the in-memory fallback."""
    global _redis_ok, _redis_cooldown_until
    now = time.monotonic()
    if _redis_ok is not False and now >= _redis_cooldown_until:
        try:
            allowed = await _allow_via_redis(key, limit)
            _redis_ok = True
            return allowed
        except Exception as exc:
            _redis_ok = False
            _redis_cooldown_until = now + _REDIS_RETRY_AFTER
            logger.warning(
                "Rate limiter: Redis unavailable, falling back to in-memory: %s", exc
            )
    return await _allow_via_memory(key, limit)


async def is_allowed(client_ip: str, bucket: str = "invoke") -> bool:
    """Return True if a request from ``client_ip`` may proceed.

    ``bucket`` names the per-IP accounting window (e.g. ``"invoke"`` for tool
    calls, ``"chat"`` for chat WebSocket messages) so each surface gets its
    own per-IP budget. The global budget is shared across ALL buckets — that
    is the real cap on total DeepSeek spend, so a client rotating IPs (or a
    second surface) still cannot push total spend past
    ``rate_limit_global_per_minute``.
    """
    if not settings.rate_limit_enabled:
        return True

    # Per-IP bucket first: this is the usual access control signal.
    ip_key = f"{client_ip}:{bucket}"
    ip_limit = max(settings.rate_limit_per_minute, 1)
    if not await _check(ip_key, ip_limit):
        return False

    # Global budget second: caps total spend across every client and surface.
    global_limit = max(settings.rate_limit_global_per_minute, 1)
    return await _check("global", global_limit)
