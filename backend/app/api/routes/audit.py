"""Audit log API (operator-facing).

Public metadata view of tool-call audit records with optional filters, plus a
per-tool usage summary for the dashboard. Raw details require an operator token.
"""

import secrets

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ok
from app.db.session import get_db
from app.models import ToolCallRecord
from app.services.audit import (
    count_tool_calls,
    list_tool_calls,
    summarize_tool_calls,
)

router = APIRouter()


def _record_to_dict(record: ToolCallRecord, *, include_details: bool = False) -> dict:
    return {
        "id": record.id,
        "tool_id": record.tool_id,
        "success": record.success,
        "input_data": record.input_data if include_details else None,
        "output_data": record.output_data if include_details else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _authorize_details(request: Request) -> None:
    if not settings.audit_operator_token:
        raise AppError(
            "Audit details access is not configured",
            code="AUDIT_DETAILS_DISABLED",
            status_code=403,
        )

    scheme, _, credential = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        credential, settings.audit_operator_token
    ):
        raise AppError(
            "Valid operator credentials are required",
            code="UNAUTHORIZED",
            status_code=401,
        )


@router.get("/summary")
async def audit_summary(db: AsyncSession = Depends(get_db)):
    """Per-tool call/failure totals for the usage dashboard."""
    by_tool = await summarize_tool_calls(db)
    total = sum(t["calls"] for t in by_tool)
    return ok({"total": total, "by_tool": by_tool})


@router.get("/tool-calls")
async def list_tool_calls_endpoint(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    tool_id: str | None = None,
    success: bool | None = None,
    include_details: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if include_details:
        _authorize_details(request)

    limit = max(1, min(limit, 500))
    offset = max(offset, 0)
    records = await list_tool_calls(
        db, limit=limit, offset=offset, tool_id=tool_id, success=success
    )
    total = await count_tool_calls(db, tool_id=tool_id, success=success)
    return ok(
        {
            "records": [_record_to_dict(r, include_details=include_details) for r in records],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    )
