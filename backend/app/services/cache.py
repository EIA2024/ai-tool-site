"""Async Redis cache with a race-safe lazy client and graceful degradation.

Every operation degrades gracefully when Redis is unreachable: callers get
``None`` (or ``False``) instead of an exception, so the cache never takes
down a request. ``get_redis`` is safe under concurrent first access.
"""

import asyncio
import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None
_redis_lock = asyncio.Lock()


async def get_redis() -> Redis:
    """Return the shared client, creating it exactly once (race-safe)."""
    global _redis
    if _redis is None:
        async with _redis_lock:
            if _redis is None:
                _redis = Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    health_check_interval=30,
                )
    return _redis


async def close_redis() -> None:
    """Close the shared client (called on app shutdown)."""
    global _redis
    if _redis is not None:
        try:
            await _redis.close()
        except Exception:
            pass
        _redis = None


async def ping() -> bool:
    try:
        r = await get_redis()
        await r.ping()
        return True
    except Exception:
        return False


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    try:
        r = await get_redis()
        await r.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        return True
    except RedisError as exc:
        logger.warning("cache_set(%s) failed: %s", key, exc)
        return False


async def cache_get(key: str) -> Any | None:
    try:
        r = await get_redis()
        data = await r.get(key)
        if data is None:
            return None
        return json.loads(data)
    except RedisError as exc:
        logger.warning("cache_get(%s) failed: %s", key, exc)
        return None


async def cache_delete(key: str) -> bool:
    try:
        r = await get_redis()
        await r.delete(key)
        return True
    except RedisError as exc:
        logger.warning("cache_delete(%s) failed: %s", key, exc)
        return False
