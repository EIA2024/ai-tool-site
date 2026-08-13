import logging
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import RedisError

from app.services import cache


@pytest.fixture
def redis_client(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(cache, "get_redis", AsyncMock(return_value=client))
    return client


@pytest.mark.asyncio
async def test_cache_get_returns_none_for_invalid_json(redis_client, caplog):
    redis_client.get.return_value = "{invalid"

    with caplog.at_level(logging.WARNING, logger=cache.__name__):
        result = await cache.cache_get("broken-key")

    assert result is None
    assert "cache_get(broken-key)" in caplog.text
    assert "JSON" in caplog.text


@pytest.mark.asyncio
async def test_cache_set_returns_false_for_unserializable_value(redis_client, caplog):
    value = {"items": {1, 2}}

    with caplog.at_level(logging.WARNING, logger=cache.__name__):
        result = await cache.cache_set("unserializable-key", value)

    assert result is False
    redis_client.set.assert_not_awaited()
    assert "cache_set(unserializable-key)" in caplog.text
    assert "JSON" in caplog.text


@pytest.mark.asyncio
async def test_cache_get_redis_error_behavior_is_unchanged(redis_client, caplog):
    redis_client.get.side_effect = RedisError("redis unavailable")

    with caplog.at_level(logging.WARNING, logger=cache.__name__):
        result = await cache.cache_get("redis-key")

    assert result is None
    assert "cache_get(redis-key) failed: redis unavailable" in caplog.text


@pytest.mark.asyncio
async def test_cache_set_redis_error_behavior_is_unchanged(redis_client, caplog):
    redis_client.set.side_effect = RedisError("redis unavailable")

    with caplog.at_level(logging.WARNING, logger=cache.__name__):
        result = await cache.cache_set("redis-key", {"ok": True})

    assert result is False
    assert "cache_set(redis-key) failed: redis unavailable" in caplog.text
