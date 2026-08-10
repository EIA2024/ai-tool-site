"""Shared DeepSeek chat-completion client.

One key-resolution rule and one error taxonomy for every DeepSeek caller
(Task Decomposer, the WS chat, future tools). Tools that need deterministic
JSON wrap :func:`chat_completion` with their own schema validation and retry
on top.
"""

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
) -> str:
    """Run one DeepSeek completion and return the assistant's content string.

    Raises ``DeepSeekError``; check ``retryable`` for the retry policy.
    """
    key = api_key or resolve_api_key()
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format:
        body["response_format"] = response_format
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
