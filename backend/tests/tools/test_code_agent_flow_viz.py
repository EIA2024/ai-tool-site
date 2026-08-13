"""Tests for the Code Agent Flow Visualizer plugin.

The old ``BaseTool.handle_invoke(action, ...)`` seam is gone; operations are now
named Pydantic handlers reached through the Host runtime. These tests drive the
handlers directly with a ``ToolContext`` and pin the input-model validation that
the Host performs before dispatch.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.tool_host.contracts import ToolContext
from app.tool_plugins.code_agent_flow_viz.plugin import (
    ImportRecordInput,
    ImportRecordsInput,
    ListRecordsInput,
    RecordIdInput,
    SaveRecordInput,
    delete_record_item,
    get_record_item,
    import_record_items,
    list_record_items,
    plugin,
    save_record,
)
from app.tool_plugins.code_agent_flow_viz.repository import count_records


def _rec(stage, user, agent="o", feedback="f", next_steps="n"):
    return ImportRecordInput(
        stage_key=stage,
        user_input=user,
        agent_output=agent,
        feedback=feedback,
        next_steps=next_steps,
    )


def test_manifest_advertises_operations():
    manifest = plugin.manifest()
    ids = [op.id for op in manifest.operations]
    assert ids == [
        "save_record",
        "list_records",
        "get_record",
        "delete_record",
        "import_records",
    ]
    assert manifest.id == "code_agent_flow_viz"
    assert manifest.ui.kind.value == "custom"
    assert manifest.ui.layout.value == "fullscreen"


@pytest.mark.asyncio
async def test_list_records_paginated_with_total(db):
    """list_records pages (limit/offset) and reports the true total so the UI
    count and the export path never silently truncate at the default 200."""
    await import_record_items(
        ImportRecordsInput(records=[_rec("s0", "u"), _rec("s1", "u"), _rec("s2", "u")]),
        ToolContext(db=db),
    )
    await db.commit()

    page1 = await list_record_items(ListRecordsInput(limit=2), ToolContext(db=db))
    assert len(page1.records) == 2
    assert page1.total == 3

    page2 = await list_record_items(
        ListRecordsInput(limit=2, offset=2), ToolContext(db=db)
    )
    assert len(page2.records) == 1
    assert page2.total == 3

    # Newest-first: page1 head is the last-imported record.
    assert page1.records[0].stage_key == "s2"


@pytest.mark.asyncio
async def test_list_records_empty_total_zero(db):
    result = await list_record_items(ListRecordsInput(), ToolContext(db=db))
    assert result.records == []
    assert result.total == 0


@pytest.mark.asyncio
async def test_import_records_ok(db):
    result = await import_record_items(
        ImportRecordsInput(records=[_rec("s1", "u1"), _rec("s2", "u2")]),
        ToolContext(db=db),
    )
    await db.commit()

    assert (result.imported, result.skipped) == (2, 0)
    assert await count_records(db) == 2


@pytest.mark.asyncio
async def test_import_records_empty_returns_zero(db):
    result = await import_record_items(ImportRecordsInput(records=[]), ToolContext(db=db))
    assert (result.imported, result.skipped) == (0, 0)


@pytest.mark.asyncio
async def test_save_record_creates_and_dedupes(db):
    first = await save_record(
        SaveRecordInput(stage_key="s1", user_input="u"), ToolContext(db=db)
    )
    await db.commit()
    assert first.created is True
    assert first.record.id

    second = await save_record(
        SaveRecordInput(stage_key="s1", user_input="u"), ToolContext(db=db)
    )
    await db.commit()
    assert second.created is False
    assert second.record.id == first.record.id


@pytest.mark.asyncio
async def test_get_and_delete_record(db):
    saved = await save_record(SaveRecordInput(stage_key="s1", user_input="u"), ToolContext(db=db))
    await db.commit()

    fetched = await get_record_item(RecordIdInput(id=saved.record.id), ToolContext(db=db))
    assert fetched.record.stage_key == "s1"

    deleted = await delete_record_item(RecordIdInput(id=saved.record.id), ToolContext(db=db))
    assert deleted.deleted is True
    assert await count_records(db) == 0


# ── Input-model validation (performed by the Host before dispatch) ──


def test_import_records_requires_list():
    with pytest.raises(PydanticValidationError):
        ImportRecordsInput.model_validate({"records": "not-a-list"})


def test_import_records_non_dict_item_rejected():
    with pytest.raises(PydanticValidationError):
        ImportRecordsInput.model_validate({"records": ["not-a-dict"]})


def test_import_records_missing_stage_key_rejected():
    with pytest.raises(PydanticValidationError):
        ImportRecordsInput.model_validate({"records": [{"user_input": "u"}]})


def test_import_records_oversized_field_rejected():
    with pytest.raises(PydanticValidationError):
        ImportRecordsInput.model_validate(
            {"records": [{"stage_key": "s", "user_input": "x" * 10001}]}
        )


def test_import_records_over_cap_rejected():
    batch = [{"stage_key": f"s{i}", "user_input": "u"} for i in range(501)]
    with pytest.raises(PydanticValidationError):
        ImportRecordsInput.model_validate({"records": batch})


def test_import_records_coerces_non_string_fields():
    """A numeric stage_key / user_input is coerced to a string (the same
    before-validator the single-save path uses) instead of failing validation."""
    model = ImportRecordsInput.model_validate(
        {"records": [{"stage_key": 123, "user_input": 12345}]}
    )
    assert model.records[0].stage_key == "123"
    assert model.records[0].user_input == "12345"
