"""Tests for the practice-record service (Code Agent Flow Visualizer)."""

import pytest

from app.services.practice_records import (
    count_records,
    create_record,
    delete_record,
    get_by_hash,
    get_record,
    list_records,
)


@pytest.mark.asyncio
async def test_create_and_get(db):
    record, created = await create_record(
        db, "stage1", "user input", "agent output", "feedback", "next steps"
    )
    await db.commit()
    assert created is True
    assert record.stage_key == "stage1"
    assert record.content_hash  # deterministic sha256

    fetched = await get_record(db, record.id)
    assert fetched is not None
    assert fetched.user_input == "user input"
    assert fetched.agent_output == "agent output"


@pytest.mark.asyncio
async def test_duplicate_returns_existing_record(db):
    r1, created1 = await create_record(db, "s", "u", "o", "f", "n")
    await db.commit()
    r2, created2 = await create_record(db, "s", "u", "o", "f", "n")
    await db.commit()
    assert created1 is True
    assert created2 is False
    assert r1.id == r2.id  # dedup by content hash


@pytest.mark.asyncio
async def test_list_and_count(db):
    await create_record(db, "s1", "a", "b", "c", "d")
    await create_record(db, "s2", "x", "y", "z", "w")
    await db.commit()

    assert await count_records(db) == 2
    records = await list_records(db)
    assert len(records) == 2
    # newest first
    assert records[0].stage_key == "s2"


@pytest.mark.asyncio
async def test_list_pagination(db):
    for i in range(5):
        await create_record(db, f"s{i}", str(i), "o", "f", "n")
    await db.commit()

    page = await list_records(db, limit=2, offset=1)
    assert len(page) == 2


@pytest.mark.asyncio
async def test_get_by_hash(db):
    record, _ = await create_record(db, "s", "u", "o", "f", "n")
    await db.commit()
    found = await get_by_hash(db, record.content_hash)
    assert found is not None
    assert found.id == record.id


@pytest.mark.asyncio
async def test_delete(db):
    record, _ = await create_record(db, "s", "u", "o", "f", "n")
    await db.commit()

    assert await delete_record(db, record.id) is True
    assert await delete_record(db, record.id) is False
    assert await get_record(db, record.id) is None
