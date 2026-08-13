"""Code Agent Flow Visualizer plugin operations."""

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

from app.core.errors import NotFoundError
from app.tool_host.contracts import (
    OperationDefinition,
    ToolContext,
    ToolPlugin,
    ToolUi,
    Transport,
    UiKind,
    UiLayout,
)
from app.tool_plugins.code_agent_flow_viz.models import AgentPracticeRecord
from app.tool_plugins.code_agent_flow_viz.repository import (
    count_records,
    create_record,
    delete_record,
    get_record,
    import_records,
    list_records,
)


def _string(value: Any) -> str:
    return str(value or "")


Text = Annotated[str, BeforeValidator(_string), Field(max_length=10_000)]
StageKey = Annotated[
    str,
    BeforeValidator(_string),
    Field(min_length=1, max_length=64),
]
RecordId = Annotated[
    str,
    BeforeValidator(_string),
    Field(min_length=1, max_length=64),
]


class PracticeRecordData(BaseModel):
    id: str
    stage_key: str
    user_input: str
    agent_output: str
    feedback: str
    next_steps: str
    content_hash: str
    created_at: str | None
    updated_at: str | None


class SaveRecordInput(BaseModel):
    stage_key: StageKey
    user_input: Text = ""
    agent_output: Text = ""
    feedback: Text = ""
    next_steps: Text = ""


class SaveRecordOutput(BaseModel):
    record: PracticeRecordData
    created: bool


class ListRecordsInput(BaseModel):
    limit: int = Field(default=200, ge=1, le=1000)
    offset: int = Field(default=0, ge=0, le=1_000_000)


class ListRecordsOutput(BaseModel):
    records: list[PracticeRecordData]
    total: int


class RecordIdInput(BaseModel):
    id: RecordId


class GetRecordOutput(BaseModel):
    record: PracticeRecordData


class DeleteRecordOutput(BaseModel):
    deleted: bool


class ImportRecordInput(BaseModel):
    stage_key: StageKey
    user_input: Text = ""
    agent_output: Text = ""
    feedback: Text = ""
    next_steps: Text = ""


class ImportRecordsInput(BaseModel):
    records: list[ImportRecordInput] = Field(max_length=500)


class ImportRecordsOutput(BaseModel):
    imported: int
    skipped: int


def _record_data(record: AgentPracticeRecord) -> PracticeRecordData:
    return PracticeRecordData(
        id=record.id,
        stage_key=record.stage_key,
        user_input=record.user_input,
        agent_output=record.agent_output,
        feedback=record.feedback,
        next_steps=record.next_steps,
        content_hash=record.content_hash,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


async def save_record(
    payload: SaveRecordInput, context: ToolContext
) -> SaveRecordOutput:
    record, created = await create_record(context.db, **payload.model_dump())
    return SaveRecordOutput(record=_record_data(record), created=created)


async def list_record_items(
    payload: ListRecordsInput, context: ToolContext
) -> ListRecordsOutput:
    records = await list_records(context.db, limit=payload.limit, offset=payload.offset)
    return ListRecordsOutput(
        records=[_record_data(record) for record in records],
        total=await count_records(context.db),
    )


async def get_record_item(
    payload: RecordIdInput, context: ToolContext
) -> GetRecordOutput:
    record = await get_record(context.db, payload.id)
    if record is None:
        raise NotFoundError("Record not found")
    return GetRecordOutput(record=_record_data(record))


async def delete_record_item(
    payload: RecordIdInput, context: ToolContext
) -> DeleteRecordOutput:
    if not await delete_record(context.db, payload.id):
        raise NotFoundError("Record not found")
    return DeleteRecordOutput(deleted=True)


async def import_record_items(
    payload: ImportRecordsInput, context: ToolContext
) -> ImportRecordsOutput:
    imported, skipped = await import_records(
        context.db,
        [record.model_dump() for record in payload.records],
    )
    return ImportRecordsOutput(imported=imported, skipped=skipped)


plugin = ToolPlugin(
    id="code_agent_flow_viz",
    version="1.0.0",
    name="Code Agent Flow Visualizer",
    description="Explore nine coding-agent workflow stages and save practice records",
    ui=ToolUi(kind=UiKind.CUSTOM, layout=UiLayout.FULLSCREEN),
    operations=(
        OperationDefinition(
            "save_record",
            Transport.REQUEST_RESPONSE,
            SaveRecordInput,
            SaveRecordOutput,
            save_record,
        ),
        OperationDefinition(
            "list_records",
            Transport.REQUEST_RESPONSE,
            ListRecordsInput,
            ListRecordsOutput,
            list_record_items,
        ),
        OperationDefinition(
            "get_record",
            Transport.REQUEST_RESPONSE,
            RecordIdInput,
            GetRecordOutput,
            get_record_item,
        ),
        OperationDefinition(
            "delete_record",
            Transport.REQUEST_RESPONSE,
            RecordIdInput,
            DeleteRecordOutput,
            delete_record_item,
        ),
        OperationDefinition(
            "import_records",
            Transport.REQUEST_RESPONSE,
            ImportRecordsInput,
            ImportRecordsOutput,
            import_record_items,
        ),
    ),
)
