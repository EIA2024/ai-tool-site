"""Unit tests for the shared model-provider client and registry.

Regression for the "DeepSeek 返回空内容" bug: V4 reasoning models default to
high-effort thinking, which counts toward ``max_tokens``. A request that
over-thinks ends with ``finish_reason="length"`` and zero ``content`` deltas.
The stream must (a) pass ``reasoning_effort`` through to the API body, and
(b) report that truncation distinctly from a genuinely empty reply.

Also pins the multi-provider contract: adding an OpenAI-compatible provider is
a ``LLM_PROVIDERS`` config change only — the client resolves the provider by
model id, points at the provider's ``base_url`` with its own key, and gates the
V4 thinking extensions on ``supports_thinking``.
"""

import json
import logging

import httpx
import pytest

from app.core.config import settings
from app.services.llm import (
    ProviderError,
    chat_completion,
    chat_completion_stream,
    get_default_model,
    get_models,
    resolve_provider,
)

# A second OpenAI-compatible provider, proving the registry is data-driven.
# ``api_key_env`` points at the existing ``deepseek_api_key`` Settings field:
# adding a provider in production also adds its own key field (see the docs
# handbook) — the resolution rule ``getattr(settings, api_key_env)`` is what
# these tests exercise, so reusing an existing field keeps the test clean.
_GLM_ENTRY = {
    "id": "glm",
    "name": "Zhipu GLM",
    "base_url": "https://open.bigmodel.cn/api/paas",
    "api_key_env": "deepseek_api_key",
    "models": ["glm-4-plus", "glm-4-air"],
    "default_model": "glm-4-plus",
    "max_output_tokens": 8192,
    "context_length": 128_000,
    "session_key_prefix": "",
    "supports_thinking": False,
}
_TWO_PROVIDERS = json.dumps(
    [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "api_key_env": "deepseek_api_key",
            "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
            "default_model": "deepseek-v4-flash",
            "max_output_tokens": 384_000,
            "context_length": 1_000_000,
            "session_key_prefix": "sk-",
            "supports_thinking": True,
        },
        _GLM_ENTRY,
    ],
    ensure_ascii=False,
)


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
    def __init__(
        self, lines=None, json_data=None, status_code=200, text=""
    ):
        self._lines = lines or []
        self._json = json_data
        self.status_code = status_code
        self.text = text

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    def json(self):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeClient:
    """Double for httpx.AsyncClient; records ``(method, url, kwargs)``."""

    def __init__(
        self, lines=None, json_data=None, status_code=200, text=""
    ):
        self.calls = []
        self._lines = lines or []
        self._json = json_data
        self._status_code = status_code
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return _FakeResponse(
            lines=self._lines,
            status_code=self._status_code,
            text=self._text,
        )

    async def post(self, url, **kwargs):
        # httpx's post() is a coroutine; match that shape so `await` works.
        self.calls.append(("POST", url, kwargs))
        return _FakeResponse(
            json_data=self._json,
            status_code=self._status_code,
            text=self._text,
        )


@pytest.fixture
def fake_client(monkeypatch):
    """Point ``httpx.AsyncClient`` at a fake that captures the request."""

    def install(
        lines=None, json_data=None, status_code=200, text=""
    ) -> _FakeClient:
        client = _FakeClient(
            lines=lines,
            json_data=json_data,
            status_code=status_code,
            text=text,
        )
        monkeypatch.setattr(
            "app.services.llm.httpx.AsyncClient",
            lambda **kwargs: client,
        )
        return client

    return install


def _body(client: _FakeClient) -> dict:
    return client.calls[0][2]["json"]


def _request(client: _FakeClient) -> tuple[str, dict, dict]:
    method, url, kwargs = client.calls[0]
    return url, kwargs["headers"], kwargs["json"]


async def _collect(gen) -> list[str]:
    return [d async for d in gen]


@pytest.mark.asyncio
async def test_api_key_overrides_server_key(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    client = fake_client(json_data={"choices": [{"message": {"content": "ok"}}]})

    await chat_completion(
        [{"role": "user", "content": "hi"}],
        "deepseek-v4-flash",
        api_key="trusted-internal-key",
    )

    assert _request(client)[1]["Authorization"] == "Bearer trusted-internal-key"


@pytest.mark.asyncio
async def test_session_api_key_is_overridden_by_server_key(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    client = fake_client(json_data={"choices": [{"message": {"content": "ok"}}]})

    await chat_completion(
        [{"role": "user", "content": "hi"}],
        "deepseek-v4-flash",
        session_api_key="sk-session",
    )

    assert _request(client)[1]["Authorization"] == "Bearer sk-server"


@pytest.mark.asyncio
async def test_session_api_key_falls_back_when_server_key_missing(
    monkeypatch, fake_client
):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    client = fake_client(json_data={"choices": [{"message": {"content": "ok"}}]})

    await chat_completion(
        [{"role": "user", "content": "hi"}],
        "deepseek-v4-flash",
        session_api_key="sk-session",
    )

    assert _request(client)[1]["Authorization"] == "Bearer sk-session"


@pytest.mark.asyncio
async def test_invalid_session_api_key_is_rejected_without_server_key(
    monkeypatch, fake_client
):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    client = fake_client(json_data={"choices": [{"message": {"content": "ok"}}]})

    with pytest.raises(ProviderError, match="sk-"):
        await chat_completion(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            session_api_key="invalid-session-key",
        )

    assert client.calls == []


@pytest.mark.asyncio
async def test_stream_api_key_overrides_server_key(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))

    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            api_key="trusted-internal-key",
        )
    )

    assert _request(client)[1]["Authorization"] == "Bearer trusted-internal-key"


@pytest.mark.asyncio
async def test_stream_session_api_key_is_overridden_by_server_key(
    monkeypatch, fake_client
):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))

    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            session_api_key="sk-session",
        )
    )

    assert _request(client)[1]["Authorization"] == "Bearer sk-server"


@pytest.mark.asyncio
async def test_stream_session_api_key_falls_back_when_server_key_missing(
    monkeypatch, fake_client
):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))

    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            session_api_key="sk-session",
        )
    )

    assert _request(client)[1]["Authorization"] == "Bearer sk-session"


@pytest.mark.asyncio
async def test_stream_invalid_session_api_key_is_rejected_without_server_key(
    monkeypatch, fake_client
):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))

    with pytest.raises(ProviderError, match="sk-"):
        await _collect(
            chat_completion_stream(
                [{"role": "user", "content": "hi"}],
                "deepseek-v4-flash",
                session_api_key="invalid-session-key",
            )
        )

    assert client.calls == []


@pytest.mark.asyncio
async def test_sync_upstream_error_hides_body_from_client_and_log(
    monkeypatch, fake_client, caplog
):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    body = '{"error":"quota exhausted","api_key":"sk-upstream-secret"}'
    fake_client(status_code=429, text=body)

    with caplog.at_level(logging.WARNING, logger="app.services.llm"):
        with pytest.raises(ProviderError) as excinfo:
            await chat_completion(
                [{"role": "user", "content": "hi"}],
                "deepseek-v4-flash",
            )

    assert str(excinfo.value) == "模型服务返回错误：HTTP 429"
    assert excinfo.value.retryable is False
    assert "HTTP 429" in caplog.text
    assert "quota exhausted" not in caplog.text
    assert "sk-upstream-secret" not in caplog.text


@pytest.mark.asyncio
async def test_upstream_error_string_cannot_leak_secrets_to_log(
    monkeypatch, fake_client, caplog
):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    body = json.dumps(
        {
            "error": (
                "request failed with Bearer bearer-secret, "
                "key sk-plain-string-secret, password=hunter2"
            )
        }
    )
    fake_client(status_code=500, text=body)

    with caplog.at_level(logging.WARNING, logger="app.services.llm"):
        with pytest.raises(ProviderError):
            await chat_completion(
                [{"role": "user", "content": "hi"}],
                "deepseek-v4-flash",
            )

    assert "HTTP 500" in caplog.text
    assert "Bearer" not in caplog.text
    assert "bearer-secret" not in caplog.text
    assert "sk-plain-string-secret" not in caplog.text
    assert "hunter2" not in caplog.text


@pytest.mark.asyncio
async def test_stream_upstream_error_does_not_log_body(
    monkeypatch, caplog
):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    response = httpx.Response(
        503,
        stream=httpx.ByteStream(
            b'{"error":"temporary failure","api_key":"sk-upstream-secret"}'
        ),
        request=httpx.Request("POST", "https://test.local"),
    )

    class _StreamingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            class _ResponseContext:
                async def __aenter__(self):
                    return response

                async def __aexit__(self, *exc):
                    await response.aclose()
                    return False

            return _ResponseContext()

    monkeypatch.setattr(
        "app.services.llm.httpx.AsyncClient",
        lambda **kwargs: _StreamingClient(),
    )

    with caplog.at_level(logging.WARNING, logger="app.services.llm"):
        with pytest.raises(ProviderError) as excinfo:
            await _collect(
                chat_completion_stream(
                    [{"role": "user", "content": "hi"}],
                    "deepseek-v4-flash",
                )
            )

    assert str(excinfo.value) == "模型服务返回错误：HTTP 503"
    assert excinfo.value.retryable is True
    assert "HTTP 503" in caplog.text
    assert "temporary failure" not in caplog.text
    assert "sk-upstream-secret" not in caplog.text


@pytest.mark.asyncio
async def test_sync_timeout_is_wrapped_as_retryable_provider_error(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    timeout = httpx.TimeoutException(
        "request timed out",
        request=httpx.Request("POST", "https://test.local"),
    )

    class _TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, **kwargs):
            raise timeout

    monkeypatch.setattr(
        "app.services.llm.httpx.AsyncClient",
        lambda **kwargs: _TimeoutClient(),
    )

    with pytest.raises(ProviderError) as excinfo:
        await chat_completion(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
        )

    assert str(excinfo.value) == "无法连接模型服务"
    assert excinfo.value.retryable is True
    assert excinfo.value.__cause__ is timeout


@pytest.mark.asyncio
async def test_stream_read_timeout_is_wrapped_as_retryable_provider_error(
    monkeypatch,
):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-server")
    timeout = httpx.ReadTimeout(
        "stream read timed out",
        request=httpx.Request("POST", "https://test.local"),
    )

    class _TimeoutResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def aiter_lines(self):
            raise timeout
            yield

    class _TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url, **kwargs):
            return _TimeoutResponse()

    monkeypatch.setattr(
        "app.services.llm.httpx.AsyncClient",
        lambda **kwargs: _TimeoutClient(),
    )

    with pytest.raises(ProviderError) as excinfo:
        await _collect(
            chat_completion_stream(
                [{"role": "user", "content": "hi"}],
                "deepseek-v4-flash",
            )
        )

    assert str(excinfo.value) == "无法连接模型服务"
    assert excinfo.value.retryable is True
    assert excinfo.value.__cause__ is timeout


# ── Streaming parser ──


@pytest.mark.asyncio
async def test_stream_passes_reasoning_effort(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))
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
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))
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
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))
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
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
        )
    )
    assert "thinking" not in _body(client)


@pytest.mark.asyncio
async def test_stream_clamps_max_tokens_to_provider_ceiling(monkeypatch, fake_client):
    """A caller asking for more than the provider's documented output cap is
    clamped, so the API limit can never be exceeded by a misconfigured
    max_tokens."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}],
            "deepseek-v4-flash",
            max_tokens=500_000,
        )
    )
    assert _body(client)["max_tokens"] == resolve_provider(
        "deepseek-v4-flash"
    ).max_output_tokens


@pytest.mark.asyncio
async def test_stream_omits_reasoning_effort_when_absent(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(lines=_sse({"content": "ok"}, finish="stop"))
    await _collect(
        chat_completion_stream(
            [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
        )
    )
    assert "reasoning_effort" not in _body(client)


@pytest.mark.asyncio
async def test_stream_yields_content_deltas(monkeypatch, fake_client):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    fake_client(lines=_sse({"content": "你好"}, {"content": "世界"}, finish="stop"))
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
        lines=_sse({"reasoning_content": "思考…"}, {"content": "答案"}, finish="stop")
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
        lines=_sse({"reasoning_content": "需要"}, {"reasoning_content": "计算"}, finish="length")
    )
    gen = chat_completion_stream(
        [{"role": "user", "content": "给我1000个随机数"}],
        "deepseek-v4-flash",
        reasoning_effort="low",
    )
    with pytest.raises(ProviderError) as excinfo:
        await _collect(gen)
    assert "思考" in str(excinfo.value)
    assert "token" in str(excinfo.value)
    assert "返回空内容" not in str(excinfo.value)


@pytest.mark.asyncio
async def test_stream_genuinely_empty_reports_generic(monkeypatch, fake_client):
    """A stream that truly returns nothing keeps the original message."""
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    fake_client(lines=_sse(finish="stop"))
    gen = chat_completion_stream(
        [{"role": "user", "content": "hi"}], "deepseek-v4-flash"
    )
    with pytest.raises(ProviderError) as excinfo:
        await _collect(gen)
    assert "返回空内容" in str(excinfo.value)


# ── Provider registry (data-driven multi-provider) ──


def test_resolve_provider_finds_model_in_second_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_providers", _TWO_PROVIDERS)
    provider = resolve_provider("glm-4-plus")
    assert provider.id == "glm"
    assert provider.base_url == "https://open.bigmodel.cn/api/paas"
    assert provider.supports_thinking is False


def test_resolve_provider_rejects_unknown_model():
    with pytest.raises(ProviderError) as excinfo:
        resolve_provider("not-a-real-model")
    assert "不支持的模型" in str(excinfo.value)
    assert "deepseek-v4-flash" in str(excinfo.value)  # lists the known models


def test_get_models_flattens_all_providers(monkeypatch):
    monkeypatch.setattr(settings, "llm_providers", _TWO_PROVIDERS)
    assert "glm-4-plus" in get_models()
    assert "deepseek-v4-flash" in get_models()


def test_get_default_model_honors_global_override(monkeypatch):
    monkeypatch.setattr(settings, "llm_default_model", "glm-4-air")
    assert get_default_model() == "glm-4-air"


@pytest.mark.asyncio
async def test_second_provider_uses_its_own_url_key_and_no_thinking(
    monkeypatch, fake_client
):
    """A non-DeepSeek provider is reached at its own base_url with its own key,
    and the V4 thinking extensions are gated off (supports_thinking=False)."""
    monkeypatch.setattr(settings, "llm_providers", _TWO_PROVIDERS)
    monkeypatch.setattr(settings, "deepseek_api_key", "glm-secret")
    client = fake_client(json_data={"choices": [{"message": {"content": "ok"}}]})
    await chat_completion(
        [{"role": "user", "content": "hi"}],
        "glm-4-plus",
        thinking=True,
        reasoning_effort="low",
    )
    url, headers, body = _request(client)
    assert url == "https://open.bigmodel.cn/api/paas/chat/completions"
    assert headers["Authorization"] == "Bearer glm-secret"
    assert "thinking" not in body
    assert "reasoning_effort" not in body


@pytest.mark.asyncio
async def test_deepseek_provider_sends_thinking_when_requested(
    monkeypatch, fake_client
):
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test")
    client = fake_client(json_data={"choices": [{"message": {"content": "ok"}}]})
    await chat_completion(
        [{"role": "user", "content": "hi"}],
        "deepseek-v4-flash",
        thinking=True,
        reasoning_effort="low",
    )
    _, _, body = _request(client)
    assert body["thinking"] == {"type": "enabled"}
    assert body["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_max_tokens_clamped_to_second_provider_ceiling(
    monkeypatch, fake_client
):
    """A provider with a smaller documented ceiling (GLM: 8K) clamps max_tokens
    to its own limit, not the DeepSeek 384K default."""
    monkeypatch.setattr(settings, "llm_providers", _TWO_PROVIDERS)
    monkeypatch.setattr(settings, "deepseek_api_key", "glm-secret")
    client = fake_client(json_data={"choices": [{"message": {"content": "ok"}}]})
    await chat_completion(
        [{"role": "user", "content": "hi"}],
        "glm-4-plus",
        max_tokens=500_000,
    )
    assert _body(client)["max_tokens"] == 8192
