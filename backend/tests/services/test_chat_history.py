"""Tests for the chat session/message history service."""

import pytest

from app.services.chat_history import (
    add_message,
    auto_title_on_first_message,
    create_session,
    delete_session,
    get_context_messages,
    get_messages,
    get_recent_sessions,
    get_session,
    prune_session_messages,
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


@pytest.mark.asyncio
async def test_context_messages_returns_newest(db):
    """A session longer than the fetch limit feeds the model the newest rows."""
    session = await create_session(db)
    await db.commit()
    for i in range(10):
        await add_message(db, session.id, "user", f"msg-{i}")
    await db.commit()

    context = await get_context_messages(db, session.id, limit=5)
    # Newest 5, chronological order.
    assert [m.content for m in context] == ["msg-5", "msg-6", "msg-7", "msg-8", "msg-9"]
    # Contrast with the naive asc fetch, which would return the OLDEST 5.
    assert [m.content for m in await get_messages(db, session.id, limit=5)] == [
        "msg-0", "msg-1", "msg-2", "msg-3", "msg-4",
    ]


@pytest.mark.asyncio
async def test_auto_title_from_first_message(db):
    session = await create_session(db, title="WebSocket Chat")
    await db.commit()

    await auto_title_on_first_message(db, session, "  帮我修一个 bug\n很紧急  ")
    assert session.title == "帮我修一个 bug 很紧急"

    # A second message (or a resumed conversation) must not re-title.
    await auto_title_on_first_message(db, session, "another one")
    assert session.title == "帮我修一个 bug 很紧急"


@pytest.mark.asyncio
async def test_auto_title_keeps_custom_title(db):
    session = await create_session(db, title="我的项目讨论")
    await db.commit()

    await auto_title_on_first_message(db, session, "hello")
    assert session.title == "我的项目讨论"


@pytest.mark.asyncio
async def test_prune_session_messages_caps_history(db):
    session = await create_session(db)
    await db.commit()
    for i in range(10):
        await add_message(db, session.id, "user", f"msg-{i}")
    await db.commit()

    deleted = await prune_session_messages(db, session.id, max_count=3)
    await db.commit()

    assert deleted == 7
    remaining = await get_messages(db, session.id)
    # The NEWEST survive; the oldest are pruned.
    assert [m.content for m in remaining] == ["msg-7", "msg-8", "msg-9"]


@pytest.mark.asyncio
async def test_prune_session_messages_under_cap_is_noop(db):
    session = await create_session(db)
    await db.commit()
    await add_message(db, session.id, "user", "only one")
    await db.commit()

    assert await prune_session_messages(db, session.id, max_count=10) == 0
    assert len(await get_messages(db, session.id)) == 1

    # Disabled cap (0) also prunes nothing.
    assert await prune_session_messages(db, session.id, max_count=0) == 0
