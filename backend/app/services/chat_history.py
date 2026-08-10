"""Chat session / message persistence (unit-of-work: no commits here).

Callers own the transaction: the API layer commits once per request.
Row ids and timestamps are generated client-side, so objects are fully
usable immediately after ``db.add`` without a refresh.
"""

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatMessage, ChatSession
from app.models.base import utcnow

VALID_ROLES = ("user", "assistant", "system")

# Titles that mean "no real title yet" — auto-titling replaces these.
DEFAULT_TITLES = ("New Chat", "WebSocket Chat")


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
    """Return the NEWEST ``limit`` messages in chronological (asc) order.

    ``offset`` counts backward from the newest (0 → the most recent page).
    Chat history is read tail-first: resuming a session shows the conversation
    as it was left, and older pages are reached by increasing ``offset``. The
    naive asc fetch would return the OLDEST rows, hiding the recent
    conversation entirely once a session grows past ``limit``. ``created_at``
    ties (same-second messages) get a deterministic secondary sort on ``id``.
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def get_context_messages(
    db: AsyncSession, session_id: str, limit: int = 200
) -> list[ChatMessage]:
    """Return the NEWEST ``limit`` messages in chronological order.

    Thin alias over :func:`get_messages` for the model-context call site.
    """
    return await get_messages(db, session_id, limit=limit)


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


async def auto_title_on_first_message(
    db: AsyncSession, session: ChatSession, content: str, max_len: int = 30
) -> None:
    """Give a session a real title from its first user message.

    Fires only when the session still carries a placeholder title AND has no
    stored messages yet, so a resumed conversation keeps its title. ``content``
    is the incoming message, which has not been stored yet at call time.
    """
    if session.title in DEFAULT_TITLES:
        existing = await db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session.id)
        )
        if not existing:
            title = " ".join(content.strip().split())[:max_len]
            if title:
                session.title = title


async def prune_session_messages(
    db: AsyncSession, session_id: str, max_count: int
) -> int:
    """Delete the oldest messages once a session exceeds ``max_count``.

    Keeps chat history bounded for long-running conversations. Returns how
    many rows were deleted (0 when under the cap or the cap is disabled).
    Call after adding the new message, before the caller commits.
    """
    if max_count <= 0:
        return 0
    count = await db.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.session_id == session_id)
    )
    if count <= max_count:
        return 0
    excess = count - max_count
    result = await db.execute(
        select(ChatMessage.id)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(excess)
    )
    ids = [row for (row,) in result.all()]
    if not ids:
        return 0
    await db.execute(delete(ChatMessage).where(ChatMessage.id.in_(ids)))
    return len(ids)


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    """Delete a session and all its messages (cascade via ORM relationship)."""
    session = await get_session(db, session_id)
    if session is None:
        return False
    await db.delete(session)
    return True
