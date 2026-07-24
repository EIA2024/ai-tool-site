import logging

from app.db.session import async_session_factory
from app.services.practice_records import (
    create_record,
    delete_record,
    get_record,
    list_records,
)
from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class CodeAgentFlowVizTool(BaseTool):
    tool_id = "code_agent_flow_viz"
    name = "Code Agent Flow Visualizer"
    description = "Explore 9 coding-agent workflow stages and save practice records"
    mode = "request-response"

    async def handle_invoke(self, payload: dict) -> dict:
        action = payload.get("action", "")
        if action not in ("save_record", "list_records", "get_record", "delete_record"):
            return {
                "success": False,
                "error": {
                    "code": "UNKNOWN_ACTION",
                    "message": (
                        f"Unknown action: '{action}'. Supported: "
                        "save_record, list_records, get_record, delete_record."
                    ),
                },
            }

        try:
            async with async_session_factory() as db:
                if action == "save_record":
                    return await self._save(db, payload)
                elif action == "list_records":
                    return await self._list(db)
                elif action == "get_record":
                    return await self._get(db, payload)
                elif action == "delete_record":
                    return await self._delete(db, payload)
        except Exception as e:
            logger.exception("CodeAgentFlowVizTool error for action=%s", action)
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                },
            }

    async def _save(self, db, payload: dict) -> dict:
        stage_key = payload.get("stage_key", "")
        if not stage_key:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Missing required field: stage_key",
                },
            }

        record, created = await create_record(
            db,
            stage_key=stage_key,
            user_input=payload.get("user_input", ""),
            agent_output=payload.get("agent_output", ""),
            feedback=payload.get("feedback", ""),
            next_steps=payload.get("next_steps", ""),
        )
        return {
            "success": True,
            "data": {
                "record": _record_to_dict(record),
                "created": created,
            },
        }

    async def _list(self, db) -> dict:
        records = await list_records(db)
        return {
            "success": True,
            "data": {
                "records": [_record_to_dict(r) for r in records],
            },
        }

    async def _get(self, db, payload: dict) -> dict:
        record_id = payload.get("id", "")
        if not record_id:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Missing required field: id",
                },
            }
        record = await get_record(db, record_id)
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
            "data": {"record": _record_to_dict(record)},
        }

    async def _delete(self, db, payload: dict) -> dict:
        record_id = payload.get("id", "")
        if not record_id:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Missing required field: id",
                },
            }
        deleted = await delete_record(db, record_id)
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
