"""Task Decomposer tool module.

Provides:
- analyze_task: call DeepSeek to decompose a task, save to history (best-effort)
- list_history: list saved analyses
- get_history: get a single analysis
- delete_history: delete an analysis
"""

import logging

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, ProviderError, ValidationError
from app.services.task_decomposer_history import (
    create_history,
    delete_history,
    get_history,
    list_history,
)
from app.tools.base import BaseTool
from app.tools.modules.task_decomposer_client import (
    AnalyzeTaskInput,
    DeepSeekClientError,
    analyze_with_deepseek,
)

logger = logging.getLogger(__name__)

_SUPPORTED_ACTIONS = ("analyze_task", "list_history", "get_history", "delete_history")


class TaskDecomposerTool(BaseTool):
    tool_id = "task_decomposer"
    name = "Task Decomposer"
    description = (
        "Break down vague development tasks into structured Coding Agent "
        "task cards using DeepSeek"
    )
    mode = "request-response"

    def config(self) -> dict:
        return {
            "supported_actions": list(_SUPPORTED_ACTIONS),
            "models": settings.deepseek_models_list,
            "default_model": settings.deepseek_default_model,
        }

    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        action = payload.get("action", "")
        if action not in _SUPPORTED_ACTIONS:
            raise ValidationError(
                f"Unknown action: '{action}'. Supported: "
                + ", ".join(_SUPPORTED_ACTIONS) + "."
            )

        if action == "analyze_task":
            return await self._analyze_task(db, payload)
        if action == "list_history":
            task_type = payload.get("task_type") or None
            records = await list_history(db, task_type=task_type)
            return {"records": [_history_to_dict(r) for r in records]}
        if action == "get_history":
            return {"record": _history_to_dict(await self._get_history(db, payload))}
        # delete_history
        deleted = await delete_history(db, _require_id(payload))
        if not deleted:
            raise NotFoundError("Record not found")
        return {"deleted": True}

    async def _analyze_task(self, db: AsyncSession, payload: dict) -> dict:
        raw_task = str(payload.get("raw_task") or "").strip()
        if not raw_task:
            raise ValidationError("请先输入原始任务")

        model = payload.get("model") or settings.deepseek_default_model
        if model not in settings.deepseek_models_list:
            raise ValidationError(
                f"不支持的模型 '{model}'。可选：{', '.join(settings.deepseek_models_list)}"
            )

        try:
            input_data = AnalyzeTaskInput(
                raw_task=raw_task,
                context=str(payload.get("context") or ""),
                task_type=str(payload.get("task_type") or "feature"),
                risk_hints=payload.get("risk_hints", []) or [],
                model=str(model),
                session_api_key=str(payload.get("session_api_key") or ""),
            )
        except PydanticValidationError as exc:
            raise ValidationError(f"输入校验失败：{exc}") from exc

        try:
            analysis = await analyze_with_deepseek(input_data)
        except DeepSeekClientError as exc:
            raise ProviderError(str(exc), code="DEEPSEEK_ERROR") from exc

        # Persist history best-effort: an analysis produced by the model is
        # too expensive to lose because the history insert failed. On failure
        # roll back this request's session (fresh per request) so the router
        # commit is a clean no-op, then still return the analysis.
        try:
            await create_history(
                db=db,
                raw_task=input_data.raw_task,
                context=input_data.context,
                task_type=input_data.task_type,
                model_name=input_data.model,
                risk_hints=input_data.risk_hints,
                risk_level=analysis.risk_level,
                structured_output=analysis.model_dump(),
            )
        except Exception as exc:
            logger.warning("Failed to save analysis history: %s", exc)
            await db.rollback()

        return {"analysis": _analysis_to_dict(analysis), "model": input_data.model}

    async def _get_history(self, db: AsyncSession, payload: dict):
        record = await get_history(db, _require_id(payload))
        if record is None:
            raise NotFoundError("Record not found")
        return record


def _require_id(payload: dict) -> str:
    record_id = str(payload.get("id") or "")
    if not record_id:
        raise ValidationError("Missing required field: id")
    if len(record_id) > 64:
        raise ValidationError("id 超过最大长度 64")
    return record_id


def _analysis_to_dict(analysis) -> dict:
    return {
        "goal": analysis.goal,
        "context": analysis.context,
        "constraints": analysis.constraints,
        "done_when": analysis.done_when,
        "failure_cases": analysis.failure_cases,
        "verification": analysis.verification,
        "missing_questions": analysis.missing_questions,
        "risk_level": analysis.risk_level,
        "non_goals": analysis.non_goals,
        "agent_prompt": analysis.agent_prompt,
    }


def _history_to_dict(record) -> dict:
    return {
        "id": record.id,
        "raw_task": record.raw_task,
        "context": record.context,
        "task_type": record.task_type,
        "model_name": record.model_name,
        "risk_hints": record.risk_hints if record.risk_hints else [],
        "risk_level": record.risk_level,
        "structured_output": record.structured_output,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
