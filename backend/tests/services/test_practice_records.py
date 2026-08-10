"""Tests for the practice-record service (Code Agent Flow Visualizer)."""

import pytest

from app.services.practice_records import (
    count_records,
    create_record,
    delete_record,
    get_by_hash,
    get_record,
    import_records,
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


def _rec(stage, user, agent="o", feedback="f", next_steps="n"):
    return {
        "stage_key": stage,
        "user_input": user,
        "agent_output": agent,
        "feedback": feedback,
        "next_steps": next_steps,
    }


@pytest.mark.asyncio
async def test_import_records_batch_with_interspersed_duplicates(db):
    """Duplicates (seeded + within-batch) are skipped without losing the rows
    imported before them — the savepoint isolates each row."""
    await create_record(db, "s0", "dup-input", "o", "f", "n")
    await db.commit()

    imported, skipped = await import_records(
        db,
        [
            _rec("s0", "dup-input"),  # duplicate of the seeded row
            _rec("s1", "u1"),
            _rec("s2", "u2"),
            _rec("s1", "u1"),  # duplicate within the batch
        ],
    )
    await db.commit()

    assert imported == 2
    assert skipped == 2
    # Seed + s1 + s2 all intact; the pre-existing duplicate did not abort the
    # transaction before the new rows landed.
    assert await count_records(db) == 3
    assert sorted(await list_records(db), key=lambda r: r.stage_key)[0].stage_key == "s0"


@pytest.mark.asyncio
async def test_import_records_dedup_matches_create_record(db):
    """A record first saved via create_record is skipped on re-import."""
    await create_record(db, "s", "u", "o", "f", "n")
    await db.commit()

    imported, skipped = await import_records(db, [_rec("s", "u")])
    await db.commit()

    assert imported == 0
    assert skipped == 1
    assert await count_records(db) == 1


@pytest.mark.asyncio
async def test_import_records_empty_and_coerces(db):
    imported, skipped = await import_records(db, [])
    assert (imported, skipped) == (0, 0)

    # Non-string values are coerced exactly like the single-save path.
    imported, skipped = await import_records(
        db,
        [
            {
                "stage_key": "s",
                "user_input": 123,
                "agent_output": None,
                "feedback": "",
                "next_steps": "",
            }
        ],
    )
    await db.commit()

    assert (imported, skipped) == (1, 0)
    recs = await list_records(db)
    assert recs[0].user_input == "123"
    assert recs[0].agent_output == ""
