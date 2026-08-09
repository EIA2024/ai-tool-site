"""Chat WebSocket handler.

Design (first principles):
- Origin check: browsers always send an ``Origin`` header; cross-site
  WebSocket hijacking is prevented by rejecting origins outside the CORS
  allow-list. Non-browser clients (no Origin) are allowed through so the
  endpoint stays scriptable.
- Session resume: the client may reconnect with ``?session_id=...`` and the
  same conversation continues in the same DB row.
- Timestamps come from ``utcnow()`` (naive UTC), never the deprecated
  ``datetime.utcnow()``, and messages are stored with the ``assistant`` role
  (``bot`` was normalized away in migration 004).
- Persistence is best-effort: a DB failure is logged and the echo still
  reaches the client instead of killing the socket.
"""

import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.base import utcnow
from app.services.chat_history import (
    add_message,
    create_session,
    get_session,
    touch_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_CONTENT = 10000


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    if not origin:
        # Non-browser client (curl, scripts) — allow.
        return True
    return origin.rstrip("/") in settings.cors_origins_list


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

            # Persist the user message (best-effort).
            await _persist(db, session.id, "user", content)

            reply = f"Echo: {content}"
            response = {
                "type": "message",
                "content": reply,
                "sender": "assistant",
                "timestamp": utcnow().isoformat() + "Z",
            }
            await websocket.send_text(json.dumps(response))

            await _persist(db, session.id, "assistant", reply)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected, session_id=%s", session.id)
    except Exception:
        logger.exception("WebSocket error, session_id=%s", session.id)
    finally:
        # The request-scoped session is torn down by FastAPI anyway; an
        # explicit rollback here clears any incomplete transaction cleanly.
        await db.rollback()


async def _persist(db: AsyncSession, session_id: str, role: str, content: str) -> None:
    """Add one message and commit; on failure roll back and keep going."""
    try:
        await add_message(db, session_id, role, content)
        await touch_session(db, session_id)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning(
            "Failed to persist %s message for session %s", role, session_id
        )
