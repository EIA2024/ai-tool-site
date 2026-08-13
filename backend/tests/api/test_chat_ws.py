"""WebSocket realtime-operation tests over the unified Host protocol.

The realtime gateway answers one ``send_message`` invoke with ``ready`` →
``progress`` → ``delta``* → ``result`` frames (or an ``error`` frame on a
validation/rate-limit failure). We drive ``realtime_operation`` directly with a
fake WebSocket (model call stubbed to an async generator) so everything runs in
the pytest event loop against the in-memory ``db`` fixture — no ASGI portal, no
cross-event-loop teardown flakiness.
"""

import json

import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.services.llm import ProviderError
from app.tool_host.websocket import realtime_operation
from app.tool_plugins.chat_tool.models import ChatMessage
from app.tool_plugins.chat_tool.repository import get_session


class FakeWebSocket:
    """Minimal WebSocket double: records frames, feeds incoming invokes."""

    def __init__(self, incoming=None):
        self.headers = {}
        self.sent: list[dict] = []
        self.closed: tuple[int, str] | None = None
        self._incoming = list(incoming or [])
        self._i = 0

    async def accept(self):
        pass

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = (code, reason)

    async def send_json(self, data: dict):
        self.sent.append(data)

    async def receive_text(self) -> str:
        if self._i < len(self._incoming):
            item = self._incoming[self._i]
            self._i += 1
            return item if isinstance(item, str) else json.dumps(item)
        raise WebSocketDisconnect()


def _invoke(payload: dict, request_id: str = "r1") -> dict:
    return {"type": "invoke", "request_id": request_id, "payload": payload}


def _install_model_registry(monkeypatch, models, default):
    """Swap the provider registry so the plugin's model checks see a custom set.
    Exercises the real registry path (``is_model_supported`` /
    ``get_default_model``) instead of mocking those functions."""
    monkeypatch.setattr(
        settings,
        "llm_providers",
        json.dumps(
            [
                {
                    "id": "deepseek",
                    "name": "Test",
                    "base_url": "https://test.local",
                    "api_key_env": "deepseek_api_key",
                    "models": models,
                    "default_model": default,
                    "supports_thinking": True,
                }
            ],
            ensure_ascii=False,
        ),
    )


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", False)


async def _stub_completion(messages, model, **kwargs):
    yield "你好，我是 AI 助手"


@pytest.mark.asyncio
async def test_ws_ai_reply_flow(db, monkeypatch):
    """ready → (progress → delta → result) with the model context containing the user text."""
    captured = {}

    async def _stub(messages, model, **kwargs):
        captured["model"] = model
        captured["context"] = messages
        yield "你好，我是 "
        yield "AI 助手"

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = FakeWebSocket([_invoke({"content": "你好"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    types = [f["type"] for f in ws.sent]
    assert types == ["ready", "progress", "delta", "delta", "result"]
    assert ws.sent[1]["data"]["session_id"]  # progress carries the session id

    assert captured["context"][0]["role"] == "system"
    assert any(
        m["role"] == "user" and m["content"] == "你好" for m in captured["context"]
    )

    # Each delta is its own frame; the final result joins them.
    assert ws.sent[2]["data"]["content"] == "你好，我是 "
    assert ws.sent[3]["data"]["content"] == "AI 助手"
    result = ws.sent[4]
    assert result["request_id"] == "r1"
    assert result["data"]["message"]["role"] == "assistant"
    assert result["data"]["message"]["content"] == "你好，我是 AI 助手"


@pytest.mark.asyncio
async def test_ws_honors_model_override(db, monkeypatch):
    """A per-message model override reaches the model call."""
    captured = {}

    async def _stub(messages, model, **kwargs):
        captured["model"] = model
        yield "ok"

    _install_model_registry(monkeypatch, ["alpha", "beta"], "alpha")
    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = FakeWebSocket([_invoke({"content": "hi", "model": "alpha"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert captured["model"] == "alpha"
    assert ws.closed is None


@pytest.mark.asyncio
async def test_ws_rejects_unknown_model(db, monkeypatch):
    """A model outside the configured list is rejected with an error frame and
    the model is never called (no paid spend, socket stays alive)."""
    calls = {"n": 0}

    async def _stub(messages, model, **kwargs):
        calls["n"] += 1
        yield "ok"

    _install_model_registry(monkeypatch, ["alpha", "beta"], "alpha")
    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = FakeWebSocket([_invoke({"content": "hi", "model": "not-a-real-model"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert calls["n"] == 0
    types = [f["type"] for f in ws.sent]
    assert types == ["ready", "error"]
    assert "不支持的模型" in ws.sent[-1]["data"]["message"]
    assert ws.closed is None


@pytest.mark.asyncio
async def test_ws_default_model_when_absent(db, monkeypatch):
    """Without a model override, the configured default is used."""
    captured = {}

    async def _stub(messages, model, **kwargs):
        captured["model"] = model
        yield "ok"

    _install_model_registry(monkeypatch, ["alpha", "beta"], "beta")
    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = FakeWebSocket([_invoke({"content": "hi"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert captured["model"] == "beta"
    assert ws.closed is None


@pytest.mark.asyncio
async def test_ws_conversation_memory_in_context(db, monkeypatch):
    """Prior stored messages are fed back to the model as context. The client
    passes the session id it learned from the first result on the next invoke."""
    seen = []

    async def _stub(messages, model, **kwargs):
        seen.append(messages)
        yield "ok"

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    first = FakeWebSocket([_invoke({"content": "我叫小明"})])
    await realtime_operation(first, "chat_tool", "send_message", db)
    sid = first.sent[-1]["data"]["session_id"]

    second = FakeWebSocket([_invoke({"content": "我叫什么？", "session_id": sid})])
    await realtime_operation(second, "chat_tool", "send_message", db)

    assert len(seen) == 2
    second_context = [m["content"] for m in seen[1]]
    assert "我叫小明" in second_context
    assert "我叫什么？" in second_context


@pytest.mark.asyncio
async def test_ws_surfaces_ai_failure_and_keeps_socket(db, monkeypatch):
    """A model failure sends an honest assistant message, socket stays alive."""
    async def _fail(messages, model, **kwargs):
        raise ProviderError("无法连接模型服务", retryable=True)
        yield  # unreachable — makes this an async generator

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _fail)
    ws = FakeWebSocket([_invoke({"content": "hi"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert ws.closed is None  # socket not killed
    result = ws.sent[-1]
    assert result["type"] == "result"
    assert "AI 调用失败" in result["data"]["message"]["content"]


@pytest.mark.asyncio
async def test_ws_empty_stream_degrades_gracefully(db, monkeypatch):
    """A stream that yields nothing still produces a visible assistant message."""
    async def _empty(messages, model, **kwargs):
        if False:
            yield  # async generator that never yields content

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _empty)
    ws = FakeWebSocket([_invoke({"content": "hi"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert ws.closed is None
    result = ws.sent[-1]
    assert result["type"] == "result"
    assert "AI 调用失败" in result["data"]["message"]["content"]


@pytest.mark.asyncio
async def test_ws_passes_chat_budget_and_thinking_policy(db, monkeypatch):
    """The chat model call uses the configured budget and disables thinking by
    default — V4 thinking burn otherwise truncates long answers."""
    captured = {}

    async def _stub(messages, model, **kwargs):
        captured.update(kwargs)
        yield "ok"

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = FakeWebSocket([_invoke({"content": "hi"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert captured["max_tokens"] == settings.chat_max_tokens
    assert captured["thinking"] is False  # thinking off unless configured on
    assert captured["reasoning_effort"] is None  # effort only sent with thinking


@pytest.mark.asyncio
async def test_ws_passes_effort_when_thinking_enabled(db, monkeypatch):
    """Re-enabling thinking in chat also sends a capped reasoning effort."""
    monkeypatch.setattr(settings, "chat_thinking", True)
    monkeypatch.setattr(settings, "chat_reasoning_effort", "low")
    captured = {}

    async def _stub(messages, model, **kwargs):
        captured.update(kwargs)
        yield "ok"

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = FakeWebSocket([_invoke({"content": "hi"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert captured["thinking"] is True
    assert captured["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_ws_passes_session_api_key(db, monkeypatch):
    """A transient per-session key reaches the model call (used in place of
    the server key, exactly like Task Decomposer's session_api_key)."""
    captured = {}

    async def _stub(messages, model, **kwargs):
        captured.update(kwargs)
        yield "ok"

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = FakeWebSocket([_invoke({"content": "hi", "session_api_key": "sk-session"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert captured["api_key"] == "sk-session"
    assert ws.closed is None


@pytest.mark.asyncio
async def test_ws_reasoning_truncation_surfaces_honest_message(db, monkeypatch):
    """A reasoning-truncated reply reaches the user as an honest message."""
    async def _truncated(messages, model, **kwargs):
        raise ProviderError(
            "模型思考过久，答案生成前已用尽 token 预算。请缩小请求范围后重试。",
            retryable=True,
        )
        yield  # unreachable — makes this an async generator

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _truncated)
    ws = FakeWebSocket([_invoke({"content": "给我1000个随机数"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert ws.closed is None
    result = ws.sent[-1]
    assert result["type"] == "result"
    assert "思考过久" in result["data"]["message"]["content"]
    assert "token" in result["data"]["message"]["content"]


@pytest.mark.asyncio
async def test_ws_stream_closes_generator_on_client_drop(db, monkeypatch):
    """If the client vanishes mid-stream, the gateway closes the generator so
    its transport is released instead of lingering until GC."""
    closed = {"n": 0}

    async def _stub(messages, model, **kwargs):
        try:
            yield "第一段"
            yield "第二段"
        finally:
            closed["n"] += 1

    class _DropWebSocket(FakeWebSocket):
        """Dies on the second delta — simulates a client gone mid-stream."""

        async def send_json(self, data):
            if data.get("type") == "delta" and self.sent:
                raise ConnectionResetError("client gone")
            self.sent.append(data)

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    ws = _DropWebSocket([_invoke({"content": "hi"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert closed["n"] == 1  # generator closed by the gateway's finally


@pytest.mark.asyncio
async def test_ws_persists_user_and_assistant(db, monkeypatch):
    """Both roles land in the DB for history reload."""
    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub_completion)
    ws = FakeWebSocket([_invoke({"content": "persist me"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    rows = result.scalars().all()
    roles = [r.role for r in rows]
    assert roles == ["user", "assistant"]
    contents = [r.content for r in rows]
    assert "persist me" in contents
    assert "你好，我是 AI 助手" in contents


@pytest.mark.asyncio
async def test_ws_resumes_existing_session(db, monkeypatch):
    """Passing a session id continues the same conversation."""
    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub_completion)

    first = FakeWebSocket([_invoke({"content": "hello"})])
    await realtime_operation(first, "chat_tool", "send_message", db)
    sid = first.sent[-1]["data"]["session_id"]

    second = FakeWebSocket([_invoke({"content": "again", "session_id": sid})])
    await realtime_operation(second, "chat_tool", "send_message", db)

    assert second.sent[-1]["data"]["session_id"] == sid
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    rows = result.scalars().all()
    # 2 messages from the first turn + 2 from the resumed turn.
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_ws_invalid_session_id_starts_fresh(db, monkeypatch):
    """A bogus session id must not crash the socket — it silently falls back to
    a brand-new session."""
    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub_completion)

    ws = FakeWebSocket([_invoke({"content": "hello", "session_id": "not-a-real-session"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    sid = ws.sent[-1]["data"]["session_id"]
    assert sid != "not-a-real-session"
    assert ws.closed is None
    result = await db.execute(select(ChatMessage).order_by(ChatMessage.created_at))
    rows = result.scalars().all()
    assert len(rows) == 2  # user + assistant persisted under the new session


@pytest.mark.asyncio
async def test_ws_autotitles_session_from_first_message(db, monkeypatch):
    """The session title is derived from the first user message."""
    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub_completion)
    ws = FakeWebSocket([_invoke({"content": "  帮我写一个登录功能  "})])
    await realtime_operation(ws, "chat_tool", "send_message", db)
    sid = ws.sent[-1]["data"]["session_id"]

    session = await get_session(db, sid)
    assert session.title == "帮我写一个登录功能"


@pytest.mark.asyncio
async def test_ws_client_ip_honors_proxy_trust(monkeypatch):
    """The WS rate-limit identity follows the same trust rule as the REST layer."""
    from types import SimpleNamespace

    from app.tool_host.gateway import client_ip

    fake = SimpleNamespace(
        headers={"x-forwarded-for": "9.9.9.9"},
        client=SimpleNamespace(host="1.1.1.1"),
    )
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert client_ip(fake) == "1.1.1.1"  # spoofed XFF ignored

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    assert client_ip(fake) == "9.9.9.9"  # trusted proxy path used


def test_trim_context_bounds_model_memory():
    """The context fed to the model stays within the char budget, keeping the
    newest messages — and always at least the most recent one."""
    from app.tool_plugins.chat_tool.plugin import _trim_context

    big = {"role": "user", "content": "x" * 1000}
    tiny = {"role": "user", "content": "y"}

    trimmed = _trim_context([big, big, tiny], budget=1100)
    assert trimmed == [big, tiny]  # oldest 1k-char message dropped

    # A single message larger than the budget is still kept (never empty).
    huge = {"role": "user", "content": "z" * 5000}
    assert _trim_context([huge], budget=1000) == [huge]


@pytest.mark.asyncio
async def test_ws_surfaces_non_deepseek_stream_error_and_keeps_socket(db, monkeypatch):
    """A malformed upstream line (a non-ProviderError exception mid-stream) must
    not kill the socket — it degrades to an honest failure message."""
    async def _bomb(messages, model, **kwargs):
        yield "部分回复"
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad bytes")
        yield  # unreachable — makes this an async generator

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _bomb)
    ws = FakeWebSocket([_invoke({"content": "hi"})])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    assert ws.closed is None
    types = [f["type"] for f in ws.sent]
    # The delta that streamed in before the error is visible, then the final
    # result frame reports the failure rather than the partial reply.
    assert types.count("delta") == 1
    result = ws.sent[-1]
    assert result["type"] == "result"
    assert "AI 调用失败" in result["data"]["message"]["content"]


@pytest.mark.asyncio
async def test_ws_rate_limited_skips_model_and_keeps_socket(db, monkeypatch):
    """Over-budget messages get an error frame; the model is not called."""
    calls = {"n": 0}

    async def _stub(messages, model, **kwargs):
        calls["n"] += 1
        yield "ok"

    async def _deny_second_message(ip, *, bucket="invoke"):
        return calls["n"] < 1

    monkeypatch.setattr("app.tool_plugins.chat_tool.plugin.chat_completion_stream", _stub)
    monkeypatch.setattr("app.tool_host.websocket.is_allowed", _deny_second_message)

    ws = FakeWebSocket(
        [_invoke({"content": "first"}, "r1"), _invoke({"content": "second"}, "r2")]
    )
    await realtime_operation(ws, "chat_tool", "send_message", db)

    # Only the first message reached the model.
    assert calls["n"] == 1
    # The rate-limited second message produced an error frame and the socket
    # stayed open.
    types = [f["type"] for f in ws.sent]
    assert types.count("error") == 1
    assert ws.closed is None


@pytest.mark.asyncio
async def test_ws_request_response_operation_rejected(db):
    """A request-response operation must be reached over REST, not WebSocket."""
    ws = FakeWebSocket([_invoke({"input": "hi"})])
    await realtime_operation(ws, "blank_tool", "echo", db)

    # No `ready` frame: the transport mismatch is reported and the socket closes.
    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "error"
    assert ws.closed is not None
    assert ws.closed[0] == 1008


@pytest.mark.asyncio
async def test_ws_invalid_frame_keeps_socket_alive(db):
    """A non-``invoke`` frame is a validation error, not a crash."""
    ws = FakeWebSocket(['{"type":"message","content":"hi"}'])
    await realtime_operation(ws, "chat_tool", "send_message", db)

    types = [f["type"] for f in ws.sent]
    assert types == ["ready", "error"]
    assert ws.closed is None
