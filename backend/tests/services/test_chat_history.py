"""Tests for the chat session/message history service."""

import pytest

from app.services.chat_history import (
    add_message,
    create_session,
    delete_session,
    get_messages,
    get_recent_sessions,
    get_session,
    touch_session,
)


@pytest.mark.asyncio
async def test_create_and_get_session(db):
    session = await create_session(db, title="Hello", tool_id="chat_tool")
    await db.commit()

    assert session.id is not None
    fetched = await get_session(db, session.id)
    assert fetched is not None
    assert fetched.title == "Hello"
    assert fetched.tool_id == "chat_tool"


@pytest.mark.asyncio
async def test_add_and_list_messages(db):
    session = await create_session(db)
    await db.commit()

    await add_message(db, session.id, "user", "hi")
    await add_message(db, session.id, "assistant", "echo: hi")
    await db.commit()

    msgs = await get_messages(db, session.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == "hi"
    assert msgs[1].content == "echo: hi"


@pytest.mark.asyncio
async def test_add_message_rejects_invalid_role(db):
    session = await create_session(db)
    await db.commit()

    with pytest.raises(ValueError):
        await add_message(db, session.id, "bot", "hi")


@pytest.mark.asyncio
async def test_recent_sessions_orders_by_touch(db):
    s1 = await create_session(db, title="first")
    s2 = await create_session(db, title="second")
    await db.commit()

    # Touch the older session so it surfaces first.
    await touch_session(db, s1.id)
    await db.commit()

    recent = await get_recent_sessions(db)
    assert [s.id for s in recent] == [s1.id, s2.id]


@pytest.mark.asyncio
async def test_delete_session_cascades_messages(db):
    session = await create_session(db)
    await db.commit()
    await add_message(db, session.id, "user", "hi")
    await db.commit()

    assert await delete_session(db, session.id) is True
    await db.commit()

    assert await get_session(db, session.id) is None
    assert await get_messages(db, session.id) == []
    assert await delete_session(db, session.id) is False
