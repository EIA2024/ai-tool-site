"""Chat WebSocket handler.

Design (first principles):
- Origin check: browsers always send an ``Origin`` header; cross-site
  WebSocket hijacking is prevented by rejecting origins outside the CORS
  allow-list. Non-browser clients (no Origin) are allowed through so the
  endpoint stays scriptable.
- Session resume: the client may reconnect with ``?session_id=...`` and the
  same conversation continues in the same DB row.
- Real AI replies: each user message is answered by DeepSeek, with the last
  ``_CONTEXT_LIMIT`` stored messages as conversation memory. The user sees a
  ``typing`` frame while the model works, then ``chunk`` frames carrying the
  reply as it streams in, and finally a ``message`` frame with the full text.
- Timestamps come from ``utcnow()`` (naive UTC), never the deprecated
  ``datetime.utcnow()``, and messages are stored with the ``assistant`` role
  (``bot`` was normalized away in migration 004).
- Persistence is best-effort: a DB failure is logged and the reply still
  reaches the client instead of killing the socket.
"""

import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import is_allowed
from app.db.session import get_db
from app.models.base import utcnow
from app.services.chat_history import (
    add_message,
    auto_title_on_first_message,
    create_session,
    get_context_messages,
    get_session,
    prune_session_messages,
    touch_session,
)
from app.services.deepseek import DeepSeekError, chat_completion_stream

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_CONTENT = 10000
_CONTEXT_LIMIT = 20  # most recent stored messages fed to the model as memory
_MAX_CONTEXT_FETCH = 200  # rows pulled (asc), tail taken — oldest are skipped
# Cap the combined memory fed to the model. 20 messages at the 10k cap would
# be ~200k chars (~50k+ tokens) — far past the model context window, turning
# an honest long chat into a hard model error. Trim to the newest messages
# that fit this budget instead (the current user message is always kept).
_CONTEXT_CHAR_BUDGET = 24_000


def _trim_context(context: list[dict], budget: int = _CONTEXT_CHAR_BUDGET) -> list[dict]:
    """Keep the newest messages whose combined length fits ``budget`` chars."""
    kept: list[dict] = []
    used = 0
    for message in reversed(context):
        cost = len(message["content"]) + 32  # rough per-message overhead
        if used + cost > budget and kept:
            break
        kept.append(message)
        used += cost
    return list(reversed(kept))

_SYSTEM_PROMPT = (
    "你是一个友好的 AI 助手，运行在用户的 AI 工具站里，通过 WebSocket 聊天。"
    "用中文回答，简洁准确，除代码外不需要 Markdown 排版。"
)


def _map_role(role: str) -> str:
    """DB roles user/assistant/system map 1:1; anything else is user-like."""
    return role if role in ("user", "assistant", "system") else "user"


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        # Non-browser client (curl, scripts) — allow.
        return True
    return origin.rstrip("/") in settings.cors_origins_list


def _client_ip(websocket: WebSocket) -> str:
    """Client address for rate limiting; mirrors the REST layer's rule.

    ``X-Forwarded-For`` is only trusted when running behind a reverse proxy
    (``TRUST_PROXY_HEADERS=true``); otherwise a client could spoof the header
    to rotate identities and bypass per-IP rate limiting. ``websocket.client``
    is ``(host, port)`` on a live socket but may be absent in tests/doubles,
    so look it up defensively.
    """
    if settings.trust_proxy_headers:
        forwarded = websocket.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    client = getattr(websocket, "client", None)
    return client.host if client else "unknown"


@router.websocket("/chat")
async def chat_websocket(
    websocket: WebSocket, db: AsyncSession = Depends(get_db)
):
    if not _origin_allowed(websocket):
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    await websocket.accept()

    # Resume an existing session or start a new one.
    session_id = websocket.query_params.get("session_id")
    session = None
    if session_id:
        session = await get_session(db, session_id)
    if session is None:
        session = await create_session(db, title="WebSocket Chat", tool_id="chat_tool")
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Failed to persist new chat session")
            await websocket.close(code=1011, reason="Could not start session")
            return

    await websocket.send_text(
        json.dumps(
            {
                "type": "connected",
                "session_id": session.id,
                # Advertise the model choice so the client can render a picker
                # without a separate config fetch.
                "models": settings.deepseek_models_list,
                "default_model": settings.deepseek_default_model,
            }
        )
    )

    try:
        while True:
            data = await websocket.receive_text()
            model = ""
            # ``json.loads`` succeeds for *any* JSON — a bare array, string,
            # number or null is valid JSON but has no ``.get``. Guard with an
            # isinstance check so such a message is treated as raw text content
            # instead of crashing the socket on an AttributeError.
            try:
                parsed = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, dict):
                content = str(parsed.get("content", ""))
                model = str(parsed.get("model") or "").strip()
            else:
                content = data
            content = content.strip()

            if not content:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "empty content"})
                )
                continue
            if len(content) > _MAX_CONTENT:
                await websocket.send_text(
                    json.dumps(
                        {"type": "error", "message": f"content exceeds {_MAX_CONTENT} chars"}
                    )
                )
                continue

            # A per-message model override must be one of the configured models;
            # anything else is rejected before the (paid, rate-limited) call.
            if model and model not in settings.deepseek_models_list:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "message": (
                                f"不支持的模型 '{model}'。可选："
                                f"{', '.join(settings.deepseek_models_list)}"
                            ),
                        }
                    )
                )
                continue

            # Every message triggers a paid DeepSeek call, so the socket is
            # rate-limited like any other spend surface (per-IP bucket + the
            # shared global budget). On over-budget we tell the client and
            # skip the model call — the socket stays alive for the next try.
            if not await is_allowed(_client_ip(websocket), bucket="chat"):
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "请求过于频繁，请稍后再试"})
                )
                continue

            # Build conversation context BEFORE persisting so ordering never
            # depends on timestamp granularity (same-second messages can share
            # created_at). The last _CONTEXT_LIMIT stored messages plus this one.
            try:
                history = await get_context_messages(db, session.id, limit=_MAX_CONTEXT_FETCH)
            except Exception:
                logger.warning(
                    "Failed to load chat context for session %s", session.id, exc_info=True
                )
                history = []
            context = [
                {"role": _map_role(m.role), "content": m.content}
                for m in history[-_CONTEXT_LIMIT:]
            ]
            context = _trim_context(context)
            context.append({"role": "user", "content": content})

            # Persist the user message (best-effort).
            await _persist(db, session, "user", content)

            # Tell the client we are working so it can show a typing state.
            await websocket.send_text(json.dumps({"type": "typing"}))

            # Stream the reply: a chunk frame per delta so the client can
            # render as the model types, then a message frame carrying the full
            # text — that full text is what gets persisted and what history
            # reload returns, so streamed and restored chats look identical.
            chunks: list[str] = []
            reply = ""
            stream = chat_completion_stream(
                [{"role": "system", "content": _SYSTEM_PROMPT}] + context,
                model or settings.deepseek_default_model,
            )
            try:
                async for delta in stream:
                    chunks.append(delta)
                    await websocket.send_text(
                        json.dumps({"type": "chunk", "content": delta})
                    )
                reply = "".join(chunks)
            except DeepSeekError as exc:
                # Keep the socket alive; surface a visible, honest message.
                # (Also covers the retryable empty-stream error above.)
                reply = f"（AI 调用失败：{exc}）"
                logger.warning("Chat AI failure for session %s: %s", session.id, exc)
            finally:
                # Release the transport even if the client dropped mid-stream
                # (a send failing mid-generator would otherwise leave the
                # httpx connection open until GC).
                await stream.aclose()

            if not reply.strip():
                # Defense in depth: an empty reply (e.g. a caller that yielded
                # nothing) must not produce an empty assistant bubble.
                reply = "（AI 调用失败：模型返回了空回复）"

            response = {
                "type": "message",
                "content": reply,
                "sender": "assistant",
                "timestamp": utcnow().isoformat() + "Z",
            }
            await websocket.send_text(json.dumps(response))

            await _persist(db, session, "assistant", reply)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected, session_id=%s", session.id)
    except Exception:
        logger.exception("WebSocket error, session_id=%s", session.id)
    finally:
        # The request-scoped session is torn down by FastAPI anyway; an
        # explicit rollback here clears any incomplete transaction cleanly.
        await db.rollback()


async def _persist(db: AsyncSession, session, role: str, content: str) -> None:
    """Add one message and commit; on failure roll back and keep going.

    The session object is passed in so auto-titling can update it in-place
    (ORM dirty-tracking persists the title with the same commit).
    """
    try:
        if role == "user":
            await auto_title_on_first_message(db, session, content)
        await add_message(db, session.id, role, content)
        await prune_session_messages(
            db, session.id, settings.chat_max_messages_per_session
        )
        await touch_session(db, session.id)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning(
            "Failed to persist %s message for session %s", role, session.id
        )
