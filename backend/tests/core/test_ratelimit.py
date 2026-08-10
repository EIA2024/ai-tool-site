"""Unit tests for the rate limiter (in-memory fallback + Redis cooldown).

These touch module-global state, so each test snapshots and restores
``_memory`` / ``_redis_ok`` / ``_redis_cooldown_until`` to avoid leaking
into the API tests.
"""

from collections import deque

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
async def test_memory_prune_negative_overflow_preserves_live_keys(monkeypatch):
    """Idle-eviction landing just under the cap must not wipe the live store.

    The old ``list(_memory)[:overflow]`` with a *negative* overflow sliced
    from the end — keeping only the newest keys. E.g. 11 keys where idle
    eviction drops 3, overflow = 11-3-10 = -2, and the slice kept only the
    last 2 keys, destroying 6 live buckets.
    """
    monkeypatch.setattr(ratelimit, "_MEMORY_MAX_KEYS", 10)
    for i in range(8):
        assert await ratelimit._allow_via_memory(f"live{i}", limit=1) is True
    for i in range(3):
        ratelimit._memory[f"idle{i}"] = deque()  # empty deque = idle key
    assert len(ratelimit._memory) == 11  # over the cap

    await ratelimit._allow_via_memory("new-key", limit=1)

    # Every live bucket survives; only idle keys were pruned.
    for i in range(8):
        assert f"live{i}" in ratelimit._memory
    assert "new-key" in ratelimit._memory
    assert len(ratelimit._memory) <= ratelimit._MEMORY_MAX_KEYS + 1


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


@pytest.mark.asyncio
async def test_is_allowed_buckets_have_independent_ip_limits(monkeypatch):
    """Per-IP budgets are separate per bucket but share one global budget."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 100)
    monkeypatch.setattr(ratelimit, "_redis_ok", False)

    # Exhaust the "invoke" bucket for this IP.
    assert await ratelimit.is_allowed("1.1.1.1", bucket="invoke") is True
    assert await ratelimit.is_allowed("1.1.1.1", bucket="invoke") is True
    assert await ratelimit.is_allowed("1.1.1.1", bucket="invoke") is False
    # The "chat" bucket is independent — still has its own budget.
    assert await ratelimit.is_allowed("1.1.1.1", bucket="chat") is True

    # Global budget is shared across buckets: clear the counters, then with
    # a budget of 1 the first caller (via invoke) fills it and a second
    # caller (via chat) is denied.
    ratelimit._memory.clear()
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 1)
    assert await ratelimit.is_allowed("9.9.9.9", bucket="invoke") is True
    assert await ratelimit.is_allowed("8.8.8.8", bucket="chat") is False
