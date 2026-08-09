"""Unit tests for the rate limiter (in-memory fallback + Redis cooldown).

These touch module-global state, so each test snapshots and restores
``_memory`` / ``_redis_ok`` / ``_redis_cooldown_until`` to avoid leaking
into the API tests.
"""

import pytest

from app.core import ratelimit


@pytest.fixture(autouse=True)
def _save_limiter_state():
    saved_memory = dict(ratelimit._memory)
    saved_ok = ratelimit._redis_ok
    saved_cooldown = ratelimit._redis_cooldown_until
    ratelimit._memory.clear()  # start clean — API tests may have left buckets
    yield
    ratelimit._memory.clear()
    ratelimit._memory.update(saved_memory)
    ratelimit._redis_ok = saved_ok
    ratelimit._redis_cooldown_until = saved_cooldown


@pytest.mark.asyncio
async def test_memory_allows_then_denies_within_window():
    assert await ratelimit._allow_via_memory("k", limit=3) is True
    assert await ratelimit._allow_via_memory("k", limit=3) is True
    assert await ratelimit._allow_via_memory("k", limit=3) is True
    assert await ratelimit._allow_via_memory("k", limit=3) is False
    assert await ratelimit._allow_via_memory("k", limit=3) is False


@pytest.mark.asyncio
async def test_memory_window_expiry_allows_again(monkeypatch):
    # A zero-length window means every timestamp is instantly stale, so the
    # deque is popped before the count check — the request is always allowed.
    monkeypatch.setattr(ratelimit, "_WINDOW_SECONDS", 0)
    for _ in range(5):
        assert await ratelimit._allow_via_memory("k", limit=2) is True


@pytest.mark.asyncio
async def test_memory_prunes_when_over_budget(monkeypatch):
    monkeypatch.setattr(ratelimit, "_MEMORY_MAX_KEYS", 10)
    # Pre-fill one entry per key so none are "idle" (deque non-empty). The
    # prune runs at the start of a call, so the size is bounded by MAX+1.
    for i in range(40):
        await ratelimit._allow_via_memory(f"ip{i}", limit=1)

    await ratelimit._allow_via_memory("new-key", limit=1)
    assert len(ratelimit._memory) <= ratelimit._MEMORY_MAX_KEYS + 1
    assert "new-key" in ratelimit._memory


@pytest.mark.asyncio
async def test_redis_failure_flags_cooldown_and_uses_memory(monkeypatch):
    calls = {"n": 0}

    async def boom(key, limit):
        calls["n"] += 1
        raise RuntimeError("redis down")

    monkeypatch.setattr(ratelimit, "_allow_via_redis", boom)
    monkeypatch.setattr(ratelimit, "_redis_ok", True)

    # First check: Redis probe fails -> falls back to memory, sets cooldown.
    assert await ratelimit._check("k", limit=2) is True
    assert ratelimit._redis_ok is False
    assert ratelimit._redis_cooldown_until > 0
    assert calls["n"] == 1

    # Second check within the cooldown: skips Redis, stays on memory.
    assert await ratelimit._check("k", limit=2) is True
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_is_allowed_checks_global_bucket(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 100)
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 2)
    monkeypatch.setattr(ratelimit, "_redis_ok", False)

    assert await ratelimit.is_allowed("1.1.1.1") is True
    assert await ratelimit.is_allowed("2.2.2.2") is True  # distinct IP, same global budget
    assert await ratelimit.is_allowed("3.3.3.3") is False  # global budget exhausted
