"""Unit tests for the shared DeepSeek client's streaming parser.

Regression for the "DeepSeek 返回空内容" bug: V4 reasoning models default to
high-effort thinking, which counts toward ``max_tokens``. A request that
over-thinks ends with ``finish_reason="length"`` and zero ``content`` deltas.
The stream must (a) pass ``reasoning_effort`` through to the API body, and
(b) report that truncation distinctly from a genuinely empty reply.
"""

import json

import pytest

from app.core.config import settings
from app.services.deepseek import DeepSeekError, chat_completion_stream


def _sse(*deltas, finish=None):
    """Build the fake SSE lines for one completion.

    ``finish`` carries the terminal finish_reason; it is emitted on a chunk
    that has *no* delta key, exercising the parser's tolerance for that shape.
    """
    lines = []
    for delta in deltas:
        lines.append(
            f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': None}]})}"
        )
    if finish:
        lines.append(
            f"data: {json.dumps({'choices': [{'finish_reason': finish}]})}"
        )
    lines.append("data: [DONE]")
    return lines


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    def __init__(self, lines):
        self.calls = []
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _FakeResponse(self._lines)


@pytest.fixture
def fake_client(monkeypatch):
    """Point ``httpx.AsyncClient`` at a fake that captures the request body."""

    def install(lines) -> _FakeClient:
        client = _FakeClient(lines)
        monkeypatch.setattr(
            "app.services.deepseek.httpx.AsyncClient",
            lambda **kwargs: client,
        )
        return client

    return install


def _body(client: _FakeClient) -> dict:
    return client.calls[0][1]["json"]


async def _collect(gen) -> list[str]:
    return [d async for d in gen]


@pytest.mark.asyncio
async def test_stream_passes_reasoning_effort(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            reasoning_effort="low",
        )
    )
    assert _body(client)["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_stream_thinking_disabled(monkeypatch, fake_client):
    """thinking=False maps to the documented toggle and drops the effort field
    (effort is meaningless without thinking)."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            thinking=False,
            reasoning_effort="low",
        )
    )
    body = _body(client)
    assert body["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in body


@pytest.mark.asyncio
async def test_stream_thinking_enabled(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            thinking=True,
        )
    )
    assert _body(client)["thinking"] == {"type": "enabled"}


@pytest.mark.asyncio
async def test_stream_omits_thinking_when_absent(monkeypatch, fake_client):
    """None leaves thinking at the API default (on) — no thinking field sent."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
        )
    )
    assert "thinking" not in _body(client)


@pytest.mark.asyncio
async def test_stream_clamps_max_tokens_to_documented_ceiling(monkeypatch, fake_client):
    """A caller asking for more than the documented 384K output cap is clamped,
    so the API limit can never be exceeded by a misconfigured max_tokens."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            max_tokens=500_000,
        )
    )
    assert _body(client)["max_tokens"] == settings.deepseek_max_output_tokens


@pytest.mark.asyncio
async def test_stream_omits_reasoning_effort_when_absent(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
        )
    )
    assert "reasoning_effort" not in _body(client)


@pytest.mark.asyncio
async def test_stream_yields_content_deltas(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    fake_client(_sse({"content": "你好"}, {"content": "世界"}, finish="stop"))
    got = await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
        )
    )
    assert got == ["你好", "世界"]


@pytest.mark.asyncio
async def test_stream_ignores_reasoning_content(monkeypatch, fake_client):
    """Thinking deltas are not surfaced as the reply — only content counts."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    fake_client(
        _sse({"reasoning_content": "思考…"}, {"content": "答案"}, finish="stop")
    )
    got = await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
        )
    )
    assert got == ["答案"]


@pytest.mark.asyncio
async def test_stream_length_truncation_reports_thinking(monkeypatch, fake_client):
    """The reported bug: the model burned the whole budget reasoning, ended
    with finish_reason="length" and zero content. This must NOT read like a
    generic empty reply — the user should learn the model over-thought."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    fake_client(
        _sse({"reasoning_content": "需要"}, {"reasoning_content": "计算"}, finish="length")
    )
    gen = chat_completion_stream(
        [{"role": "user", "content": "给我1000个随机数"}],
        "deepseek-v4-flash",
        reasoning_effort="low",
    )
    with pytest.raises(DeepSeekError) as excinfo:
        await _collect(gen)
    assert "思考" in str(excinfo.value)
    assert "token" in str(excinfo.value)
    assert "返回空内容" not in str(excinfo.value)


@pytest.mark.asyncio
async def test_stream_genuinely_empty_reports_generic(monkeypatch, fake_client):
    """A stream that truly returns nothing keeps the original message."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    fake_client(_sse(finish="stop"))
    gen = chat_completion_stream(
        [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
    )
    with pytest.raises(DeepSeekError) as excinfo:
        await _collect(gen)
    assert "返回空内容" in str(excinfo.value)
