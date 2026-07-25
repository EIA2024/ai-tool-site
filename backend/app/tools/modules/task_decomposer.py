"""Task Decomposer tool module.

Provides:
- analyze_task: call DeepSeek to decompose a task, save to history
- list_history: list saved analyses
- get_history: get a single analysis
- delete_history: delete an analysis
"""

import logging

from app.db.session import async_session_factory
from app.services.task_decomposer_history import (
    create_history,
    delete_history,
    get_history,
    list_history,
)
from app.tools.base import BaseTool
from app.tools.modules.task_decomposer_client import (
    DeepSeekClientError,
    AnalyzeTaskInput,
    analyze_with_deepseek,
)

logger = logging.getLogger(__name__)


class TaskDecomposerTool(BaseTool):
    tool_id = "task_decomposer"
    name = "Task Decomposer"
    description = "Break down vague development tasks into structured Coding Agent task cards using DeepSeek"
    mode = "request-response"

    async def handle_invoke(self, payload: dict) -> dict:
        action = payload.get("action", "")
        if action not in ("analyze_task", "list_history", "get_history", "delete_history"):
            return {
                "success": False,
                "error": {
                    "code": "UNKNOWN_ACTION",
                    "message": (
                        f"Unknown action: '{action}'. Supported: "
                        "analyze_task, list_history, get_history, delete_history."
                    ),
                },
            }

        try:
            if action == "analyze_task":
                return await self._analyze_task(payload)
            async with async_session_factory() as db:
                if action == "list_history":
                    return await self._list_history(db, payload)
                elif action == "get_history":
                    return await self._get_history(db, payload)
                elif action == "delete_history":
                    return await self._delete_history(db, payload)
        except Exception as e:
            logger.exception("TaskDecomposerTool error for action=%s", action)
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                },
            }

    async def _analyze_task(self, payload: dict) -> dict:
        raw_task = payload.get("raw_task", "").strip()
        if not raw_task:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请先输入原始任务",
                },
            }

        input_data = AnalyzeTaskInput(
            raw_task=raw_task,
            context=payload.get("context", ""),
            task_type=payload.get("task_type", "feature"),
            risk_hints=payload.get("risk_hints", []),
            model=payload.get("model", "deepseek-v4-flash"),
            session_api_key=payload.get("session_api_key", ""),
        )

        try:
            analysis = await analyze_with_deepseek(input_data)
        except DeepSeekClientError as e:
            return {
                "success": False,
                "error": {
                    "code": "DEEPSEEK_ERROR",
                    "message": str(e),
                },
            }

        # Save to history (fire-and-forget style — errors don't fail the response)
        try:
            async with async_session_factory() as db:
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
        except Exception as e:
            logger.warning("Failed to save analysis history: %s", e)

        return {
            "success": True,
            "data": {
                "analysis": _analysis_to_dict(analysis),
                "model": input_data.model,
            },
        }

    async def _list_history(self, db, payload: dict) -> dict:
        task_type = payload.get("task_type") or None
        records = await list_history(db, task_type=task_type)
        return {
            "success": True,
            "data": {
                "records": [_history_to_dict(r) for r in records],
            },
        }

    async def _get_history(self, db, payload: dict) -> dict:
        record_id = payload.get("id", "")
        if not record_id:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Missing required field: id",
                },
            }
        record = await get_history(db, record_id)
        if record is None:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Record '{record_id}' not found",
                },
            }
        return {
            "success": True,
            "data": {"record": _history_to_dict(record)},
        }

    async def _delete_history(self, db, payload: dict) -> dict:
        record_id = payload.get("id", "")
        if not record_id:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Missing required field: id",
                },
            }
        deleted = await delete_history(db, record_id)
        if not deleted:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Record '{record_id}' not found",
                },
            }
        return {
            "success": True,
            "data": {"deleted": True},
        }


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
