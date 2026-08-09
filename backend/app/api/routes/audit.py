"""Audit log API (operator-facing).

Read-only view of tool-call audit records with optional filters.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ok
from app.db.session import get_db
from app.models import ToolCallRecord
from app.services.audit import count_tool_calls, list_tool_calls

router = APIRouter()


def _record_to_dict(record: ToolCallRecord) -> dict:
    return {
        "id": record.id,
        "tool_id": record.tool_id,
        "success": record.success,
        "input_data": record.input_data,
        "output_data": record.output_data,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get("/tool-calls")
async def list_tool_calls_endpoint(
    limit: int = 50,
    offset: int = 0,
    tool_id: str | None = None,
    success: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 500))
    offset = max(offset, 0)
    records = await list_tool_calls(
        db, limit=limit, offset=offset, tool_id=tool_id, success=success
    )
    total = await count_tool_calls(db, tool_id=tool_id, success=success)
    return ok(
        {
            "records": [_record_to_dict(r) for r in records],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )
