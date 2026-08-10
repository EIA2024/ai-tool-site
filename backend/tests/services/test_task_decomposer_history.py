"""Tests for the Task Decomposer history CRUD service.

Uses the shared in-memory ``db`` fixture from ``tests/conftest.py`` (which
disposes the engine after each test so the aiosqlite worker thread terminates).
"""

import pytest

from app.services.task_decomposer_history import (
    create_history,
    delete_history,
    get_history,
    list_history,
    prune_history,
)


@pytest.mark.asyncio
async def test_create_and_get_history(db):
    created = await create_history(
        db,
        raw_task="Test task",
        context="Test context",
        task_type="feature",
        model_name="deepseek-v4-flash",
        risk_hints=["data_loss"],
        risk_level="medium",
        structured_output={
            "goal": "Test goal",
            "context": ["ctx1"],
            "constraints": ["c1"],
            "done_when": ["d1"],
            "failure_cases": ["f1"],
            "verification": ["v1"],
            "missing_questions": [],
            "risk_level": "medium",
            "non_goals": [],
            "agent_prompt": "test prompt",
        },
    )
    await db.commit()
    assert created.id is not None
    assert created.raw_task == "Test task"
    assert created.task_type == "feature"
    assert created.risk_level == "medium"

    fetched = await get_history(db, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.structured_output["goal"] == "Test goal"


@pytest.mark.asyncio
async def test_list_history(db):
    await create_history(
        db,
        raw_task="Task A",
        context="",
        risk_hints=None,
        task_type="feature",
        model_name="m1",
        risk_level="low",
        structured_output={"goal": "a"},
    )
    await create_history(
        db,
        raw_task="Task B",
        context="",
        risk_hints=None,
        task_type="bugfix",
        model_name="m1",
        risk_level="high",
        structured_output={"goal": "b"},
    )
    await db.commit()

    all_records = await list_history(db)
    assert len(all_records) == 2

    filtered = await list_history(db, task_type="bugfix")
    assert len(filtered) == 1
    assert filtered[0].raw_task == "Task B"


@pytest.mark.asyncio
async def test_get_history_not_found(db):
    missing = await get_history(db, "nonexistent")
    assert missing is None


@pytest.mark.asyncio
async def test_delete_history(db):
    created = await create_history(
        db,
        raw_task="Delete me",
        context="",
        risk_hints=None,
        task_type="feature",
        model_name="m1",
        risk_level="low",
        structured_output={"goal": "g"},
    )
    await db.commit()
    deleted = await delete_history(db, created.id)
    assert deleted is True

    remaining = await get_history(db, created.id)
    assert remaining is None

    again = await delete_history(db, created.id)
    assert again is False


@pytest.mark.asyncio
async def test_prune_history_caps_table(db):
    """History retention mirrors the audit log: oldest rows pruned, newest kept."""
    from datetime import timedelta

    from app.models.base import utcnow

    base = utcnow()
    for i in range(5):
        rec = await create_history(
            db,
            raw_task=f"task {i}",
            context="",
            task_type="feature",
            model_name="m1",
            risk_hints=None,
            risk_level="low",
            structured_output={"goal": "g"},
        )
        # task 0 oldest … task 4 newest, so the surviving set is deterministic.
        rec.created_at = base - timedelta(hours=5 - i)
    await db.commit()

    deleted = await prune_history(db, max_count=3)
    await db.commit()

    assert deleted == 2
    remaining = await list_history(db, limit=10)
    assert sorted(r.raw_task for r in remaining) == ["task 2", "task 3", "task 4"]


@pytest.mark.asyncio
async def test_prune_history_under_cap_is_noop(db):
    await create_history(
        db,
        raw_task="only",
        context="",
        task_type="feature",
        model_name="m1",
        risk_hints=None,
        risk_level="low",
        structured_output={"goal": "g"},
    )
    await db.commit()

    # Over-cap prunes nothing; a disabled cap (0) also prunes nothing.
    assert await prune_history(db, max_count=10) == 0
    assert await prune_history(db, max_count=0) == 0
