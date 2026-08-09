"""Chat session & message history API (REST complement to /ws/chat).

Every handler commits once after the service call — matching the
unit-of-work contract (services never commit).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError, ok
from app.db.session import get_db
from app.models import ChatMessage, ChatSession
from app.services.chat_history import (
    add_message,
    create_session,
    delete_session,
    get_messages,
    get_recent_sessions,
    get_session,
    touch_session,
)

router = APIRouter()

_MAX_TITLE = 255


class CreateSessionRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=_MAX_TITLE)
    tool_id: str | None = Field(default=None, max_length=100)


def _message_to_dict(msg: ChatMessage) -> dict:
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _session_to_dict(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "tool_id": session.tool_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
    }


@router.get("/sessions")
async def list_sessions(
    limit: int = 50, db: AsyncSession = Depends(get_db)
):
    limit = max(1, min(limit, 200))
    sessions = await get_recent_sessions(db, limit=limit)
    return ok({"sessions": [_session_to_dict(s) for s in sessions]})


@router.post("/sessions")
async def new_session(
    body: CreateSessionRequest, db: AsyncSession = Depends(get_db)
):
    session = await create_session(
        db, title=body.title.strip() or "New Chat", tool_id=body.tool_id
    )
    await db.commit()
    return ok({"session": _session_to_dict(session)})


@router.get("/sessions/{session_id}")
async def get_one_session(
    session_id: str, db: AsyncSession = Depends(get_db)
):
    session = await get_session(db, session_id)
    if session is None:
        raise NotFoundError("Session not found")
    return ok({"session": _session_to_dict(session)})


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    limit: int = 200,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 1000))
    offset = max(offset, 0)
    if await get_session(db, session_id) is None:
        raise NotFoundError("Session not found")
    messages = await get_messages(db, session_id, limit=limit, offset=offset)
    return ok({"messages": [_message_to_dict(m) for m in messages]})


@router.post("/sessions/{session_id}/messages")
async def add_rest_message(
    session_id: str, body: dict, db: AsyncSession = Depends(get_db)
):
    """REST fallback for posting a single user message (WS is primary)."""
    content = body.get("content", "")
    role = body.get("role", "user")
    if not content or len(content) > 10000:
        raise ValidationError("content 必须非空且不超过 10000 字符")
    if role not in ("user", "assistant"):
        raise ValidationError("role 必须是 user 或 assistant")
    if await get_session(db, session_id) is None:
        raise NotFoundError("Session not found")
    msg = await add_message(db, session_id, role, content)
    await touch_session(db, session_id)
    await db.commit()
    return ok({"message": _message_to_dict(msg)})


@router.delete("/sessions/{session_id}")
async def remove_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session and all its messages."""
    if not await delete_session(db, session_id):
        raise NotFoundError("Session not found")
    await db.commit()
    return ok({"deleted": True})
