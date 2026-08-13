"""Shared model-provider client.

One key-resolution rule and one error taxonomy for every model caller (Task
Decomposer, the WS chat, future tools). Providers are data-driven
(``settings.llm_provider_list``): adding an OpenAI-compatible provider is a
``LLM_PROVIDERS`` entry plus a Settings field for its key — no client code.
Tools that need deterministic JSON wrap :func:`chat_completion` with their own
schema validation and retry on top.

The wire-format seam is ``ProviderConfig.api_style``. Only ``"openai`` (the
``/chat/completions`` contract) is implemented today; a future Anthropic or
Gemini native adapter would add a branch in :func:`_chat_url` /
:func:`_chat_headers` — the caller-facing functions below never change.
"""

import json
import logging

import httpx

from app.core.config import ProviderConfig, settings

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """Model-service integration failure.

    ``retryable`` marks failures where a fresh attempt has a real chance of
    succeeding (transient transport, 5xx, non-deterministic model output).
    4xx auth/quota errors are never retryable — a retry cannot fix them.
    """

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def get_providers() -> list[ProviderConfig]:
    return settings.llm_provider_list


def get_models() -> list[str]:
    """Every model across every configured provider (order preserved)."""
    return [m for p in settings.llm_provider_list for m in p.models]


def get_default_model() -> str:
    """``LLM_DEFAULT_MODEL`` if set, else the default provider's own default."""
    if settings.llm_default_model:
        return settings.llm_default_model
    for p in settings.llm_provider_list:
        if p.id == settings.llm_default_provider:
            return p.default_model
    return ""


def resolve_provider(model: str) -> ProviderConfig:
    """The provider that owns ``model``.

    Model IDs are treated as unique across providers (the first match wins);
    in practice ids like ``deepseek-v4-flash`` / ``gpt-4o`` do not collide. An
    unknown model is a config error — rejected before any paid call.
    """
    for p in settings.llm_provider_list:
        if model in p.models:
            return p
    raise ProviderError(
        f"不支持的模型 '{model}'。可选：{', '.join(get_models())}"
    )


def is_model_supported(model: str) -> bool:
    return any(model in p.models for p in settings.llm_provider_list)


def resolve_api_key(provider: ProviderConfig, session_api_key: str = "") -> str:
    """Server key from .env wins; a session key is only a fallback.

    Session keys are validated against the provider's ``session_key_prefix``
    (DeepSeek = ``"sk-"``; ``""`` accepts any non-empty key).
    """
    server_key = getattr(settings, provider.api_key_env, "")
    if server_key:
        return server_key
    if session_api_key:
        prefix = provider.session_key_prefix
        if prefix and not session_api_key.startswith(prefix):
            raise ProviderError(
                f"会话 API Key 格式无效：必须以 '{prefix}' 开头，"
                "或改用 .env 中的服务端 Key。"
            )
        return session_api_key
    raise ProviderError(
        f"未配置 {provider.name} API Key。请在 .env 中设置 "
        f"{provider.api_key_env.upper()}，或在页面输入临时 Key。"
    )


def _chat_url(provider: ProviderConfig) -> str:
    """Endpoint for one completion, per ``api_style``.

    Only ``"openai"`` (``base_url`` + ``/chat/completions``) is implemented.
    Future styles (Anthropic ``/v1/messages``, Gemini ``v1beta:generateContent``)
    add a branch here and in :func:`_chat_headers`.
    """
    if provider.api_style == "openai":
        return provider.base_url.rstrip("/") + "/chat/completions"
    raise ProviderError(f"api_style '{provider.api_style}' is not implemented")


def _chat_headers(provider: ProviderConfig, key: str) -> dict[str, str]:
    if provider.api_style == "openai":
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        headers.update(provider.extra_headers)
        return headers
    raise ProviderError(f"api_style '{provider.api_style}' is not implemented")


def _log_upstream_error(response: httpx.Response) -> None:
    logger.warning(
        "Model upstream returned HTTP %s",
        response.status_code,
    )


async def chat_completion(
    messages: list[dict[str, str]],
    model: str,
    *,
    api_key: str = "",
    session_api_key: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    response_format: dict[str, str] | None = None,
    timeout: float = 90.0,
    reasoning_effort: str | None = None,
    thinking: bool | None = None,
) -> str:
    """Run one completion and return the assistant's content string.

    ``thinking`` (``True``/``False``) toggles the provider's reasoning mode
    explicitly; ``None`` leaves it at the API default. ``reasoning_effort``
    (``"low"``/``"high"``/``"max"``) caps reasoning depth; it is dropped when
    thinking is disabled. Both are only sent to providers that advertise
    ``supports_thinking``. ``max_tokens`` is clamped to the provider's
    documented output ceiling so a misconfigured caller can't exceed the API
    limit.

    Raises ``ProviderError``; check ``retryable`` for the retry policy.
    """
    provider = resolve_provider(model)
    key = api_key or resolve_api_key(provider, session_api_key)
    # The provider caps output (e.g. DeepSeek 384K tokens); clamp defensively.
    max_tokens = min(max_tokens, provider.max_output_tokens)
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format:
        body["response_format"] = response_format
    if provider.supports_thinking:
        if reasoning_effort and thinking is not False:
            body["reasoning_effort"] = reasoning_effort
        if thinking is not None:
            body["thinking"] = {"type": "enabled" if thinking else "disabled"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                _chat_url(provider), headers=_chat_headers(provider, key), json=body
            )
    except httpx.HTTPError as exc:
        raise ProviderError("无法连接模型服务", retryable=True) from exc

    if response.status_code >= 400:
        _log_upstream_error(response)
        raise ProviderError(
            f"模型服务返回错误：HTTP {response.status_code}",
            retryable=response.status_code >= 500,
        )

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        # ValueError covers json.JSONDecodeError.
        raise ProviderError("模型返回结构异常", retryable=True) from exc

    if not content or not content.strip():
        raise ProviderError("模型返回空内容，请调整 prompt 后重试", retryable=True)

    return content


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str,
    *,
    api_key: str = "",
    session_api_key: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    response_format: dict[str, str] | None = None,
    timeout: float = 90.0,
    reasoning_effort: str | None = None,
    thinking: bool | None = None,
):
    """Run one completion with ``stream: True`` and yield content deltas as
    they arrive (async generator).

    Same error taxonomy as :func:`chat_completion` (raise ``ProviderError``,
    check ``retryable``). The caller accumulates the yielded deltas into the
    full reply — nothing is buffered here.

    ``thinking`` / ``reasoning_effort`` pass through to providers that
    ``supports_thinking`` (e.g. DeepSeek V4). Reasoning models "think" by
    default at ``high`` effort and the thinking counts toward ``max_tokens``;
    a request that over-thinks can end with ``finish_reason`` ``"length"`` and
    zero ``content`` deltas. That case is reported distinctly (the model ran
    out of budget thinking, not "returned nothing"). Chat disables thinking
    entirely to make the failure impossible.
    """
    provider = resolve_provider(model)
    key = api_key or resolve_api_key(provider, session_api_key)
    # The provider caps output (e.g. DeepSeek 384K tokens); clamp defensively.
    max_tokens = min(max_tokens, provider.max_output_tokens)
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if response_format:
        body["response_format"] = response_format
    if provider.supports_thinking:
        if reasoning_effort and thinking is not False:
            body["reasoning_effort"] = reasoning_effort
        if thinking is not None:
            body["thinking"] = {"type": "enabled" if thinking else "disabled"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream(
                "POST",
                _chat_url(provider),
                headers=_chat_headers(provider, key),
                json=body,
            ) as response:
                if response.status_code >= 400:
                    _log_upstream_error(response)
                    raise ProviderError(
                        f"模型服务返回错误：HTTP {response.status_code}",
                        retryable=response.status_code >= 500,
                    )
                yielded_any = False
                finish_reason = None
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        choice = json.loads(payload)["choices"][0]
                    except (KeyError, IndexError, TypeError, ValueError):
                        continue
                    # A final chunk may carry finish_reason with an empty delta;
                    # read both independently so a reasoning-truncated stream is
                    # diagnosed instead of silently skipped.
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]
                    delta = choice.get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yielded_any = True
                        yield content
        except httpx.HTTPError as exc:
            raise ProviderError("无法连接模型服务", retryable=True) from exc
        if not yielded_any:
            if finish_reason == "length":
                # Reasoning models spend the max_tokens budget on "thinking"
                # first; a request that over-thinks never reaches the answer
                # and ends with zero content. Distinct from a model that
                # genuinely returned nothing, so the user knows to shrink the
                # request rather than just "adjust the prompt".
                raise ProviderError(
                    "模型思考过久，答案生成前已用尽 token 预算。"
                    "请缩小请求范围后重试。",
                    retryable=True,
                )
            # Same empty-reply semantics as chat_completion: a stream that
            # produced no content is a retryable model-output failure.
            raise ProviderError(
                "模型返回空内容，请调整 prompt 后重试", retryable=True
            )
