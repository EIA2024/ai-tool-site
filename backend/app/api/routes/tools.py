"""Tool API routes.

Every invocation is wrapped in a request-scoped DB session (injected via
``Depends(get_db)``) and committed exactly once after the tool returns.
Expected business failures surface as typed ``ToolError`` and are converted
to the standard JSON envelope; every call (success or failure) is written to
the audit log so operators can see usage and failure rates.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, NotFoundError, RateLimitError, ok
from app.core.ratelimit import is_allowed
from app.core.redact import redact
from app.db.session import get_db
from app.services.audit import log_tool_call, prune_tool_calls
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

router = APIRouter()

# Cap audit payloads so a single huge invocation cannot bloat the DB.
_AUDIT_CAP = 100_000


class ToolInvokeRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


def _client_ip(request: Request) -> str:
    """Best-effort client identifier.

    ``X-Forwarded-For`` is only trusted when running behind a reverse proxy
    (``TRUST_PROXY_HEADERS=true``); otherwise a client could spoof the header
    to rotate identities and bypass per-IP rate limiting.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return request.client.host if request.client else "unknown"


def _serialize(value: Any) -> str:
    """Serialize a value for the audit log, redacting any secrets first."""
    try:
        text = json.dumps(redact(value), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return text[:_AUDIT_CAP]


@router.get("")
async def list_tools():
    return ok({"tools": tool_registry.list_tool_metadata()})


@router.get("/{tool_id}")
async def get_tool(tool_id: str):
    tool = tool_registry.get_tool(tool_id)
    if tool is None:
        raise NotFoundError(f"Tool '{tool_id}' not found")
    return ok({"tool_id": tool.tool_id, **tool.metadata(), "config": tool.config()})


@router.post("/{tool_id}/invoke")
async def invoke_tool(
    tool_id: str,
    req: ToolInvokeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tool = tool_registry.get_tool(tool_id)
    if tool is None:
        raise NotFoundError(f"Tool '{tool_id}' not found")

    if not await is_allowed(_client_ip(request)):
        raise RateLimitError()

    input_json = _serialize(req.payload)
    success = False
    output_json: str | None = None
    try:
        data = await tool.handle_invoke(req.payload, db)
        await db.commit()
        success = True
        return ok(data)
    except AppError:
        # Expected failure: record it, reset any failed transaction state,
        # then let the global handler build the envelope.
        output_json = _serialize({"success": False, "error": "see response"})
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        try:
            await log_tool_call(db, tool_id, input_json, output_json, success)
            await prune_tool_calls(db, settings.audit_max_records)
            await db.commit()
        except Exception:
            logger.warning(
                "Failed to write audit record for tool_id=%s", tool_id, exc_info=True
            )
            await db.rollback()
