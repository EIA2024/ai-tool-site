from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.services.practice_records import (
    create_record,
    delete_record,
    get_record,
    list_records,
)
from app.tools.base import BaseTool

_SUPPORTED_ACTIONS = ("save_record", "list_records", "get_record", "delete_record")


class CodeAgentFlowVizTool(BaseTool):
    tool_id = "code_agent_flow_viz"
    name = "Code Agent Flow Visualizer"
    description = "Explore 9 coding-agent workflow stages and save practice records"
    mode = "request-response"

    def config(self) -> dict:
        return {"supported_actions": list(_SUPPORTED_ACTIONS)}

    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        action = payload.get("action", "")
        if action not in _SUPPORTED_ACTIONS:
            raise ValidationError(
                f"Unknown action: '{action}'. Supported: "
                + ", ".join(_SUPPORTED_ACTIONS) + "."
            )

        if action == "save_record":
            return await self._save(db, payload)
        if action == "list_records":
            records = await list_records(db)
            return {"records": [_record_to_dict(r) for r in records]}
        if action == "get_record":
            return {"record": _record_to_dict(await self._get(db, payload))}
        # delete_record
        deleted = await delete_record(db, _require_id(payload))
        if not deleted:
            raise NotFoundError("Record not found")
        return {"deleted": True}

    async def _save(self, db: AsyncSession, payload: dict) -> dict:
        stage_key = payload.get("stage_key", "")
        if not stage_key:
            raise ValidationError("Missing required field: stage_key")
        if len(stage_key) > 64:
            raise ValidationError("stage_key 超过最大长度 64")

        record, created = await create_record(
            db,
            stage_key=stage_key,
            user_input=_bounded(payload.get("user_input", ""), "user_input"),
            agent_output=_bounded(payload.get("agent_output", ""), "agent_output"),
            feedback=_bounded(payload.get("feedback", ""), "feedback"),
            next_steps=_bounded(payload.get("next_steps", ""), "next_steps"),
        )
        return {"record": _record_to_dict(record), "created": created}

    async def _get(self, db: AsyncSession, payload: dict):
        record = await get_record(db, _require_id(payload))
        if record is None:
            raise NotFoundError("Record not found")
        return record


def _bounded(value: str, field: str) -> str:
    if len(value) > 10000:
        raise ValidationError(f"{field} 超过最大长度 10000")
    return value


def _require_id(payload: dict) -> str:
    record_id = payload.get("id", "")
    if not record_id:
        raise ValidationError("Missing required field: id")
    if len(record_id) > 64:
        raise ValidationError("id 超过最大长度 64")
    return record_id


def _record_to_dict(record) -> dict:
    return {
        "id": record.id,
        "stage_key": record.stage_key,
        "user_input": record.user_input,
        "agent_output": record.agent_output,
        "feedback": record.feedback,
        "next_steps": record.next_steps,
        "content_hash": record.content_hash,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
