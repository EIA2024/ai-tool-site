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
  ``typing`` frame while the model works.
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
from app.services.deepseek import DeepSeekError, chat_completion

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_CONTENT = 10000
_CONTEXT_LIMIT = 20  # most recent stored messages fed to the model as memory
_MAX_CONTEXT_FETCH = 200  # rows pulled (asc), tail taken — oldest are skipped

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
    """Client address for rate limiting; best-effort like the REST layer.

    ``websocket.client`` is ``(host, port)`` on a live socket but may be
    absent in tests/doubles, so look it up defensively.
    """
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
        json.dumps({"type": "connected", "session_id": session.id})
    )

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                content = str(msg.get("content", ""))
            except (json.JSONDecodeError, TypeError):
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
            context.append({"role": "user", "content": content})

            # Persist the user message (best-effort).
            await _persist(db, session, "user", content)

            # Tell the client we are working so it can show a typing state.
            await websocket.send_text(json.dumps({"type": "typing"}))

            try:
                reply = await chat_completion(
                    [{"role": "system", "content": _SYSTEM_PROMPT}] + context,
                    settings.deepseek_default_model,
                )
            except DeepSeekError as exc:
                # Keep the socket alive; surface a visible, honest message.
                reply = f"（AI 调用失败：{exc}）"
                logger.warning("Chat AI failure for session %s: %s", session.id, exc)

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
