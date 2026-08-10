"""WebSocket chat handler tests.

The handler now answers each user message with a real DeepSeek reply and a
``typing`` frame while the model works. We drive ``chat_websocket`` directly
with a fake WebSocket (model call stubbed) so everything runs in the pytest
event loop against the in-memory ``db`` fixture — no ASGI portal, no
cross-event-loop teardown flakiness.
"""

import json

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.models.chat import ChatMessage
from app.services.deepseek import DeepSeekError
from app.ws.handler import chat_websocket


class FakeWebSocket:
    """Minimal WebSocket double: records frames, feeds incoming messages."""

    def __init__(self, incoming=None, query_params=None):
        self.headers = {}
        self.query_params = query_params or {}
        self.sent: list[dict] = []
        self.closed: tuple[int, str] | None = None
        self._incoming = list(incoming or [])
        self._i = 0

    async def accept(self):
        pass

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = (code, reason)

    async def send_text(self, text: str):
        self.sent.append(json.loads(text))

    async def receive_text(self) -> str:
        if self._i < len(self._incoming):
            item = self._incoming[self._i]
            self._i += 1
            return item if isinstance(item, str) else json.dumps(item)
        raise WebSocketDisconnect()


def _user_message(content: str) -> dict:
    return {"type": "message", "content": content}


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch):
    """These tests exercise the handler, not the real limiter's shared state.

    The real per-IP/global buckets key on the client address, which every
    FakeWebSocket reports as "unknown" — so without disabling, tests would
    trip each other's limits. The rate-limit test below overrides
    ``is_allowed`` itself.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", False)


async def _stub_completion(messages, model, **kwargs):
    return "你好，我是 AI 助手"


@pytest.mark.asyncio
async def test_ws_ai_reply_flow(db, monkeypatch):
    """connected → (typing → message) with the model context containing the user text."""
    captured = {}

    async def _stub(messages, model, **kwargs):
        captured["model"] = model
        captured["context"] = messages
        return "你好，我是 AI 助手"

    monkeypatch.setattr("app.ws.handler.chat_completion", _stub)
    ws = FakeWebSocket([_user_message("你好")])
    await chat_websocket(ws, db)

    types = [f["type"] for f in ws.sent]
    assert types == ["connected", "typing", "message"]
    assert ws.sent[0].get("session_id")

    assert captured["context"][0]["role"] == "system"
    assert any(
        m["role"] == "user" and m["content"] == "你好" for m in captured["context"]
    )

    reply = ws.sent[2]
    assert reply["sender"] == "assistant"
    assert reply["content"] == "你好，我是 AI 助手"


@pytest.mark.asyncio
async def test_ws_conversation_memory_in_context(db, monkeypatch):
    """Prior stored messages are fed back to the model as context."""
    seen = []

    async def _stub(messages, model, **kwargs):
        seen.append(messages)
        return "ok"

    monkeypatch.setattr("app.ws.handler.chat_completion", _stub)
    ws = FakeWebSocket([_user_message("我叫小明"), _user_message("我叫什么？")])
    await chat_websocket(ws, db)

    assert len(seen) == 2
    second_context = [m["content"] for m in seen[1]]
    # The model sees both stored turns as context for the second reply.
    assert "我叫小明" in second_context
    assert "我叫什么？" in second_context


@pytest.mark.asyncio
async def test_ws_surfaces_ai_failure_and_keeps_socket(db, monkeypatch):
    """A DeepSeek failure sends an honest assistant message, socket stays alive."""
    async def _fail(messages, model, **kwargs):
        raise DeepSeekError("无法连接 DeepSeek API", retryable=True)

    monkeypatch.setattr("app.ws.handler.chat_completion", _fail)
    ws = FakeWebSocket([_user_message("hi")])
    await chat_websocket(ws, db)

    assert ws.closed is None  # socket not killed
    reply = ws.sent[-1]
    assert reply["type"] == "message"
    assert "AI 调用失败" in reply["content"]


@pytest.mark.asyncio
async def test_ws_persists_user_and_assistant(db, monkeypatch):
    """Both roles land in the DB for history reload."""
    monkeypatch.setattr("app.ws.handler.chat_completion", _stub_completion)
    ws = FakeWebSocket([_user_message("persist me")])
    await chat_websocket(ws, db)

    result = await db.execute(
        select(ChatMessage).order_by(ChatMessage.created_at)
    )
    rows = result.scalars().all()
    roles = [r.role for r in rows]
    assert roles == ["user", "assistant"]
    contents = [r.content for r in rows]
    assert "persist me" in contents
    assert "你好，我是 AI 助手" in contents


@pytest.mark.asyncio
async def test_ws_resumes_existing_session(db, monkeypatch):
    """Reconnecting with session_id continues the same conversation."""
    monkeypatch.setattr("app.ws.handler.chat_completion", _stub_completion)

    first = FakeWebSocket([_user_message("hello")])
    await chat_websocket(first, db)
    sid = first.sent[0]["session_id"]

    second = FakeWebSocket([_user_message("again")], query_params={"session_id": sid})
    await chat_websocket(second, db)

    assert second.sent[0]["session_id"] == sid
    result = await db.execute(
        select(ChatMessage).order_by(ChatMessage.created_at)
    )
    rows = result.scalars().all()
    # 2 messages from the first turn + 2 from the resumed turn.
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_ws_invalid_session_id_starts_fresh(db, monkeypatch):
    """A bogus session_id (ids are String columns, so lookup is a no-op) must
    not crash the socket — it silently falls back to a brand-new session."""
    monkeypatch.setattr("app.ws.handler.chat_completion", _stub_completion)

    ws = FakeWebSocket(
        [_user_message("hello")], query_params={"session_id": "not-a-real-session"}
    )
    await chat_websocket(ws, db)

    sid = ws.sent[0]["session_id"]
    assert sid != "not-a-real-session"
    assert ws.closed is None
    result = await db.execute(
        select(ChatMessage).order_by(ChatMessage.created_at)
    )
    rows = result.scalars().all()
    assert len(rows) == 2  # user + assistant persisted under the new session


@pytest.mark.asyncio
async def test_ws_autotitles_session_from_first_message(db, monkeypatch):
    """The session title is derived from the first user message."""
    from app.services.chat_history import get_session

    monkeypatch.setattr("app.ws.handler.chat_completion", _stub_completion)
    ws = FakeWebSocket([_user_message("  帮我写一个登录功能  ")])
    await chat_websocket(ws, db)
    sid = ws.sent[0]["session_id"]

    session = await get_session(db, sid)
    assert session.title == "帮我写一个登录功能"


@pytest.mark.asyncio
async def test_ws_client_ip_honors_proxy_trust(monkeypatch):
    """The WS rate-limit identity must follow the same trust rule as the REST
    layer: X-Forwarded-For is only used when TRUST_PROXY_HEADERS is set."""
    from types import SimpleNamespace

    from app.core.config import settings
    from app.ws.handler import _client_ip

    fake = SimpleNamespace(
        headers={"x-forwarded-for": "9.9.9.9"},
        client=SimpleNamespace(host="1.1.1.1"),
    )
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert _client_ip(fake) == "1.1.1.1"  # spoofed XFF ignored

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    assert _client_ip(fake) == "9.9.9.9"  # trusted proxy path used


def test_trim_context_bounds_model_memory():
    """The context fed to the model stays within the char budget, keeping the
    newest messages — and always at least the most recent one."""
    from app.ws.handler import _trim_context

    big = {"role": "user", "content": "x" * 1000}
    tiny = {"role": "user", "content": "y"}

    trimmed = _trim_context([big, big, tiny], budget=1100)
    assert trimmed == [big, tiny]  # oldest 1k-char message dropped

    # A single message larger than the budget is still kept (never empty).
    huge = {"role": "user", "content": "z" * 5000}
    assert _trim_context([huge], budget=1000) == [huge]


@pytest.mark.asyncio
async def test_ws_rate_limited_skips_model_and_keeps_socket(db, monkeypatch):
    """Over-budget messages get an error frame; the model is not called."""
    calls = {"n": 0}

    async def _stub(messages, model, **kwargs):
        calls["n"] += 1
        return "ok"

    async def _deny_second_message(ip, *, bucket="invoke"):
        return calls["n"] < 1

    monkeypatch.setattr("app.ws.handler.chat_completion", _stub)
    monkeypatch.setattr("app.ws.handler.is_allowed", _deny_second_message)

    ws = FakeWebSocket([_user_message("first"), _user_message("second")])
    await chat_websocket(ws, db)

    # Only the first message reached the model.
    assert calls["n"] == 1
    # The rate-limited second message produced an error frame and the socket
    # stayed open.
    types = [f["type"] for f in ws.sent]
    assert types.count("error") == 1
    assert ws.closed is None
    assert any(
        t == "message" for t in types
    )  # the first reply still rendered
