"""Task Decomposer plugin operations."""

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError
from app.services.llm import ProviderError as LlmProviderError
from app.services.llm import get_models, is_model_supported
from app.tool_host.contracts import (
    OperationDefinition,
    ToolContext,
    ToolPlugin,
    ToolUi,
    Transport,
    UiKind,
    UiLayout,
)
from app.tool_plugins.task_decomposer.client import (
    AnalyzeTaskInput,
    TaskAnalysis,
    analyze_with_llm,
)
from app.tool_plugins.task_decomposer.models import TaskAnalysisHistory
from app.tool_plugins.task_decomposer.repository import (
    create_history,
    delete_history,
    get_history,
    list_history,
    prune_history,
)

logger = logging.getLogger(__name__)


class AnalyzeTaskOutput(BaseModel):
    analysis: TaskAnalysis
    model: str


class ListHistoryInput(BaseModel):
    task_type: str | None = Field(default=None, max_length=20)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=1_000_000)


class HistoryRecordData(BaseModel):
    id: str
    raw_task: str
    context: str
    task_type: str
    model_name: str
    risk_hints: list[str]
    risk_level: str
    structured_output: dict[str, Any]
    created_at: str | None


class ListHistoryOutput(BaseModel):
    records: list[HistoryRecordData]


class HistoryIdInput(BaseModel):
    id: str = Field(min_length=1, max_length=64)


class GetHistoryOutput(BaseModel):
    record: HistoryRecordData


class DeleteHistoryOutput(BaseModel):
    deleted: bool


def _history_data(record: TaskAnalysisHistory) -> HistoryRecordData:
    return HistoryRecordData(
        id=record.id,
        raw_task=record.raw_task,
        context=record.context,
        task_type=record.task_type,
        model_name=record.model_name,
        risk_hints=record.risk_hints or [],
        risk_level=record.risk_level,
        structured_output=record.structured_output,
        created_at=record.created_at.isoformat() if record.created_at else None,
    )


async def analyze_task(
    payload: AnalyzeTaskInput, context: ToolContext
) -> AnalyzeTaskOutput:
    if not is_model_supported(payload.model):
        from app.core.errors import ValidationError

        raise ValidationError(
            f"不支持的模型 '{payload.model}'。可选：{', '.join(get_models())}"
        )
    try:
        analysis = await analyze_with_llm(payload)
    except LlmProviderError as exc:
        raise ProviderError(str(exc), code="LLM_ERROR") from exc

    # Saving history is best-effort: a completed paid model response must not
    # be lost merely because persistence is temporarily unavailable.
    try:
        await create_history(
            db=context.db,
            raw_task=payload.raw_task,
            context=payload.context,
            task_type=payload.task_type,
            model_name=payload.model,
            risk_hints=payload.risk_hints,
            risk_level=analysis.risk_level,
            structured_output=analysis.model_dump(),
        )
        await prune_history(context.db, settings.task_decomposer_history_max_records)
    except Exception as exc:
        logger.warning("Failed to save analysis history: %s", exc)
        await context.db.rollback()
    return AnalyzeTaskOutput(analysis=analysis, model=payload.model)


async def list_history_items(
    payload: ListHistoryInput, context: ToolContext
) -> ListHistoryOutput:
    records = await list_history(
        context.db,
        task_type=payload.task_type or None,
        limit=payload.limit,
        offset=payload.offset,
    )
    return ListHistoryOutput(records=[_history_data(record) for record in records])


async def get_history_item(
    payload: HistoryIdInput, context: ToolContext
) -> GetHistoryOutput:
    record = await get_history(context.db, payload.id)
    if record is None:
        raise NotFoundError("Record not found")
    return GetHistoryOutput(record=_history_data(record))


async def delete_history_item(
    payload: HistoryIdInput, context: ToolContext
) -> DeleteHistoryOutput:
    if not await delete_history(context.db, payload.id):
        raise NotFoundError("Record not found")
    return DeleteHistoryOutput(deleted=True)


plugin = ToolPlugin(
    id="task_decomposer",
    version="1.0.0",
    name="Task Decomposer",
    description="Turn vague development requests into structured Coding Agent task cards",
    ui=ToolUi(kind=UiKind.CUSTOM, layout=UiLayout.FULLSCREEN),
    operations=(
        OperationDefinition(
            "analyze_task",
            Transport.REQUEST_RESPONSE,
            AnalyzeTaskInput,
            AnalyzeTaskOutput,
            analyze_task,
        ),
        OperationDefinition(
            "list_history",
            Transport.REQUEST_RESPONSE,
            ListHistoryInput,
            ListHistoryOutput,
            list_history_items,
        ),
        OperationDefinition(
            "get_history",
            Transport.REQUEST_RESPONSE,
            HistoryIdInput,
            GetHistoryOutput,
            get_history_item,
        ),
        OperationDefinition(
            "delete_history",
            Transport.REQUEST_RESPONSE,
            HistoryIdInput,
            DeleteHistoryOutput,
            delete_history_item,
        ),
    ),
)
