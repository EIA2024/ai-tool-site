"""Shared DeepSeek chat-completion client.

One key-resolution rule and one error taxonomy for every DeepSeek caller
(Task Decomposer, the WS chat, future tools). Tools that need deterministic
JSON wrap :func:`chat_completion` with their own schema validation and retry
on top.
"""

import json

import httpx

from app.core.config import settings

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekError(RuntimeError):
    """DeepSeek integration failure.

    ``retryable`` marks failures where a fresh attempt has a real chance of
    succeeding (transient transport, 5xx, non-deterministic model output).
    4xx auth/quota errors are never retryable — a retry cannot fix them.
    """

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def resolve_api_key(session_api_key: str = "") -> str:
    """Server key from .env wins; a session key is only a fallback."""
    if settings.deepseek_api_key:
        return settings.deepseek_api_key
    if session_api_key:
        if not session_api_key.startswith("sk-"):
            raise DeepSeekError(
                "会话 API Key 格式无效：必须以 'sk-' 开头，或改用 .env 中的服务端 Key。"
            )
        return session_api_key
    raise DeepSeekError(
        "未配置 DeepSeek API Key。请在 .env 中设置，或在页面输入临时 Key。"
    )


async def chat_completion(
    messages: list[dict[str, str]],
    model: str,
    *,
    api_key: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    response_format: dict[str, str] | None = None,
    timeout: float = 90.0,
    reasoning_effort: str | None = None,
    thinking: bool | None = None,
) -> str:
    """Run one DeepSeek completion and return the assistant's content string.

    ``thinking`` (``True``/``False``) toggles V4 thinking mode explicitly;
    ``None`` leaves it at the API default (on). ``reasoning_effort``
    (``"low"``/``"high"``/``"max"``) caps thinking depth; it is dropped when
    thinking is disabled. ``max_tokens`` is clamped to the documented 384K
    output ceiling so a misconfigured caller can't exceed the API limit.

    Raises ``DeepSeekError``; check ``retryable`` for the retry policy.
    """
    key = api_key or resolve_api_key()
    # The API caps output at 384K tokens; clamp defensively.
    max_tokens = min(max_tokens, settings.deepseek_max_output_tokens)
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format:
        body["response_format"] = response_format
    if reasoning_effort and thinking is not False:
        body["reasoning_effort"] = reasoning_effort
    if thinking is not None:
        body["thinking"] = {"type": "enabled" if thinking else "disabled"}
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(DEEPSEEK_URL, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise DeepSeekError("无法连接 DeepSeek API", retryable=True) from exc

    if response.status_code >= 400:
        # Include the upstream detail (truncated) so operators can diagnose
        # auth/quota errors without a network trace.
        detail = (response.text or "").strip()[:300]
        suffix = f": {detail}" if detail else ""
        raise DeepSeekError(
            f"DeepSeek API 返回错误：HTTP {response.status_code}{suffix}",
            retryable=response.status_code >= 500,
        )

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        # ValueError covers json.JSONDecodeError.
        raise DeepSeekError("DeepSeek 返回结构异常", retryable=True) from exc

    if not content or not content.strip():
        raise DeepSeekError("DeepSeek 返回空内容，请调整 prompt 后重试", retryable=True)

    return content


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str,
    *,
    api_key: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    response_format: dict[str, str] | None = None,
    timeout: float = 90.0,
    reasoning_effort: str | None = None,
    thinking: bool | None = None,
):
    """Run one DeepSeek completion with ``stream: True`` and yield content
    deltas as they arrive (async generator).

    Same error taxonomy as :func:`chat_completion` (raise ``DeepSeekError``,
    check ``retryable``). The caller accumulates the yielded deltas into the
    full reply — nothing is buffered here.

    ``thinking`` / ``reasoning_effort`` pass through to the API. V4 models
    "think" by default at ``high`` effort and the thinking counts toward
    ``max_tokens``; a request that over-thinks can end with ``finish_reason``
    ``"length"`` and zero ``content`` deltas. That case is reported distinctly
    (the model ran out of budget thinking, not "returned nothing"). Chat
    disables thinking entirely to make the failure impossible.
    """
    key = api_key or resolve_api_key()
    # The API caps output at 384K tokens; clamp defensively.
    max_tokens = min(max_tokens, settings.deepseek_max_output_tokens)
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if response_format:
        body["response_format"] = response_format
    if reasoning_effort and thinking is not False:
        body["reasoning_effort"] = reasoning_effort
    if thinking is not None:
        body["thinking"] = {"type": "enabled" if thinking else "disabled"}
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream(
                "POST", DEEPSEEK_URL, headers=headers, json=body
            ) as response:
                if response.status_code >= 400:
                    # Error bodies are small; reading them here is safe even in
                    # streaming mode (we are aborting anyway).
                    detail = (response.text or "").strip()[:300]
                    suffix = f": {detail}" if detail else ""
                    raise DeepSeekError(
                        f"DeepSeek API 返回错误：HTTP {response.status_code}{suffix}",
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
            raise DeepSeekError("无法连接 DeepSeek API", retryable=True) from exc
        if not yielded_any:
            if finish_reason == "length":
                # Reasoning models spend the max_tokens budget on "thinking"
                # first; a request that over-thinks never reaches the answer
                # and ends with zero content. Distinct from a model that
                # genuinely returned nothing, so the user knows to shrink the
                # request rather than just "adjust the prompt".
                raise DeepSeekError(
                    "DeepSeek 模型思考过久，答案生成前已用尽 token 预算。"
                    "请缩小请求范围后重试。",
                    retryable=True,
                )
            # Same empty-reply semantics as chat_completion: a stream that
            # produced no content is a retryable model-output failure.
            raise DeepSeekError(
                "DeepSeek 返回空内容，请调整 prompt 后重试", retryable=True
            )
