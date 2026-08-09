"""Chat session / message persistence (unit-of-work: no commits here).

Callers own the transaction: the API layer commits once per request.
Row ids and timestamps are generated client-side, so objects are fully
usable immediately after ``db.add`` without a refresh.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession
from app.models.base import utcnow

VALID_ROLES = ("user", "assistant", "system")


async def create_session(
    db: AsyncSession, title: str = "New Chat", tool_id: str | None = None
) -> ChatSession:
    session = ChatSession(title=title, tool_id=tool_id)
    db.add(session)
    await db.flush()
    return session


async def get_session(db: AsyncSession, session_id: str) -> ChatSession | None:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def add_message(
    db: AsyncSession, session_id: str, role: str, content: str
) -> ChatMessage:
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}, got {role!r}")
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    await db.flush()
    return msg


async def get_messages(
    db: AsyncSession, session_id: str, limit: int = 200, offset: int = 0
) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_recent_sessions(
    db: AsyncSession, limit: int = 50
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def touch_session(db: AsyncSession, session_id: str) -> None:
    """Bump ``updated_at`` so the session surfaces in recent lists."""
    await db.execute(
        update(ChatSession)
        .where(ChatSession.id == session_id)
        .values(updated_at=utcnow())
    )


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    """Delete a session and all its messages (cascade via ORM relationship)."""
    session = await get_session(db, session_id)
    if session is None:
        return False
    await db.delete(session)
    return True
