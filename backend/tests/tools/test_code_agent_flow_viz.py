"""Tests for the Code Agent Flow Visualizer tool module.

Focus: the ``import_records`` batch action. It must validate the whole batch
upfront (reject malformed input without partially importing), cap the batch
size, and delegate dedup to the service's savepoint-guarded import.
"""

import pytest

from app.core.errors import ValidationError
from app.services.practice_records import count_records
from app.tools.modules.code_agent_flow_viz import (
    _IMPORT_MAX_RECORDS,
    CodeAgentFlowVizTool,
)

tool = CodeAgentFlowVizTool()


def _rec(stage, user, agent="o", feedback="f", next_steps="n"):
    return {
        "stage_key": stage,
        "user_input": user,
        "agent_output": agent,
        "feedback": feedback,
        "next_steps": next_steps,
    }


def test_config_advertises_import_records():
    assert "import_records" in tool.config()["supported_actions"]


@pytest.mark.asyncio
async def test_list_records_paginated_with_total(db):
    """list_records pages (limit/offset) and reports the true total so the UI
    count and the export path never silently truncate at the default 200."""
    for i in range(3):
        await tool.handle_invoke(
            {"action": "import_records", "records": [_rec(f"s{i}", "u")]}, db
        )
    await db.commit()

    page1 = await tool.handle_invoke(
        {"action": "list_records", "limit": 2}, db
    )
    assert len(page1["records"]) == 2
    assert page1["total"] == 3

    page2 = await tool.handle_invoke(
        {"action": "list_records", "limit": 2, "offset": 2}, db
    )
    assert len(page2["records"]) == 1
    assert page2["total"] == 3

    # Newest-first: page1 head is the last-imported record.
    assert page1["records"][0]["stage_key"] == "s2"


@pytest.mark.asyncio
async def test_list_records_invalid_limit_rejected(db):
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke(
            {"action": "list_records", "limit": "not-a-number"}, db
        )
    assert excinfo.value.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_list_records_empty_total_zero(db):
    result = await tool.handle_invoke({"action": "list_records"}, db)
    assert result["records"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_import_records_ok(db):
    result = await tool.handle_invoke(
        {"action": "import_records", "records": [_rec("s1", "u1"), _rec("s2", "u2")]},
        db,
    )
    await db.commit()

    assert result == {"imported": 2, "skipped": 0}
    assert await count_records(db) == 2


@pytest.mark.asyncio
async def test_import_records_empty_returns_zero(db):
    result = await tool.handle_invoke({"action": "import_records", "records": []}, db)
    assert result == {"imported": 0, "skipped": 0}


@pytest.mark.asyncio
async def test_import_records_requires_list(db):
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke({"action": "import_records"}, db)
    assert excinfo.value.code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_import_records_non_dict_item_rejected(db):
    with pytest.raises(ValidationError):
        await tool.handle_invoke(
            {"action": "import_records", "records": ["not-a-dict"]}, db
        )


@pytest.mark.asyncio
async def test_import_records_missing_stage_key_rejected(db):
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke(
            {"action": "import_records", "records": [_rec("", "u")]}, db
        )
    assert "stage_key" in str(excinfo.value)


@pytest.mark.asyncio
async def test_import_records_oversized_field_rejected(db):
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke(
            {
                "action": "import_records",
                "records": [_rec("s", "x" * 10001)],
            },
            db,
        )
    assert "10000" in str(excinfo.value)


@pytest.mark.asyncio
async def test_import_records_over_cap_rejected(db):
    batch = [_rec(f"s{i}", "u") for i in range(_IMPORT_MAX_RECORDS + 1)]
    with pytest.raises(ValidationError) as excinfo:
        await tool.handle_invoke({"action": "import_records", "records": batch}, db)
    assert "500" in str(excinfo.value)


@pytest.mark.asyncio
async def test_import_records_validation_failure_imports_nothing(db):
    """A malformed record anywhere in the batch aborts the whole import — no
    partial prefix is written."""
    with pytest.raises(ValidationError):
        await tool.handle_invoke(
            {
                "action": "import_records",
                "records": [_rec("s1", "ok"), _rec("s2", "x" * 10001), _rec("s3", "ok")],
            },
            db,
        )
    await db.commit()
    assert await count_records(db) == 0
