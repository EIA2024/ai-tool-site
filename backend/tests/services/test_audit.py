"""Tests for the tool-call audit service."""

from datetime import datetime, timedelta

import pytest

from app.models import ToolCallRecord
from app.services.audit import (
    count_tool_calls,
    list_tool_calls,
    log_tool_call,
    prune_tool_calls,
    summarize_tool_calls,
)


@pytest.mark.asyncio
async def test_log_and_list(db):
    await log_tool_call(db, "blank_tool", '{"input":"x"}', '{"echo":"x"}', True)
    await db.commit()

    records = await list_tool_calls(db)
    assert len(records) == 1
    assert records[0].tool_id == "blank_tool"
    assert records[0].success is True
    assert "x" in records[0].input_data


@pytest.mark.asyncio
async def test_filters(db):
    await log_tool_call(db, "blank_tool", None, None, True)
    await log_tool_call(db, "task_decomposer", None, None, False)
    await db.commit()

    assert await count_tool_calls(db) == 2
    assert await count_tool_calls(db, tool_id="blank_tool") == 1
    assert await count_tool_calls(db, success=False) == 1

    failed = await list_tool_calls(db, success=False)
    assert len(failed) == 1
    assert failed[0].tool_id == "task_decomposer"


@pytest.mark.asyncio
async def test_list_pagination(db):
    for i in range(5):
        await log_tool_call(db, f"tool_{i}", None, None, True)
    await db.commit()

    page = await list_tool_calls(db, limit=2, offset=1)
    assert len(page) == 2
    # newest first
    assert page[0].tool_id == "tool_3"
    assert page[1].tool_id == "tool_2"


@pytest.mark.asyncio
async def test_summary_groups_by_tool(db):
    await log_tool_call(db, "blank_tool", None, None, True)
    await log_tool_call(db, "task_decomposer", None, None, True)
    await log_tool_call(db, "task_decomposer", None, None, False)
    await db.commit()

    summary = await summarize_tool_calls(db)
    by_id = {row["tool_id"]: row for row in summary}

    assert by_id["blank_tool"]["calls"] == 1
    assert by_id["blank_tool"]["failures"] == 0
    assert by_id["task_decomposer"]["calls"] == 2
    assert by_id["task_decomposer"]["failures"] == 1


@pytest.mark.asyncio
async def test_prune_tool_calls_caps_count_keeping_newest(db):
    base = datetime(2026, 1, 1)
    for i in range(5):
        db.add(
            ToolCallRecord(
                tool_id=f"tool_{i}",
                input_data=None,
                output_data=None,
                success=True,
                created_at=base + timedelta(seconds=i),
            )
        )
    await db.commit()

    deleted = await prune_tool_calls(db, max_count=3)
    assert deleted == 2
    await db.commit()

    remaining = await list_tool_calls(db)
    assert len(remaining) == 3
    assert {r.tool_id for r in remaining} == {"tool_2", "tool_3", "tool_4"}


@pytest.mark.asyncio
async def test_prune_tool_calls_disabled_when_zero(db):
    for i in range(3):
        await log_tool_call(db, f"tool_{i}", None, None, True)
    await db.commit()

    assert await prune_tool_calls(db, max_count=0) == 0
    assert await count_tool_calls(db) == 3


@pytest.mark.asyncio
async def test_prune_tool_calls_under_cap_is_noop(db):
    for i in range(3):
        await log_tool_call(db, f"tool_{i}", None, None, True)
    await db.commit()

    assert await prune_tool_calls(db, max_count=10) == 0
    assert await count_tool_calls(db) == 3
