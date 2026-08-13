"""Unified REST discovery and request-response operation gateway."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, RateLimitError, ok
from app.core.ratelimit import is_allowed
from app.db.session import get_db
from app.tool_host.contracts import ToolContext
from app.tool_host.discovery import get_registry
from app.tool_host.gateway import client_ip, write_operation_audit
from app.tool_host.runtime import invoke_request_operation, resolve_operation
from app.tool_host.site import public_manifests

router = APIRouter()
registry = get_registry()


class OperationRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_tools():
    manifests = public_manifests(registry.manifests())
    return ok({"tools": [manifest.model_dump(mode="json") for manifest in manifests]})


@router.get("/{tool_id}")
async def get_tool(tool_id: str):
    plugin = registry.get(tool_id)
    if plugin is None:
        from app.core.errors import NotFoundError

        raise NotFoundError(f"Tool '{tool_id}' not found")
    return ok({"tool": plugin.manifest().model_dump(mode="json")})


@router.post("/{tool_id}/operations/{operation_id}")
async def invoke_operation(
    tool_id: str,
    operation_id: str,
    body: OperationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    operation = resolve_operation(registry, tool_id, operation_id)
    ip = client_ip(request)
    if not await is_allowed(ip, bucket=f"tool:{tool_id}:{operation_id}"):
        raise RateLimitError()

    success = False
    output: Any = None
    try:
        result = await invoke_request_operation(
            operation,
            body.payload,
            ToolContext(db=db, client_ip=ip),
        )
        await db.commit()
        output = result.model_dump(mode="json")
        success = True
        return ok(output)
    except AppError as exc:
        await db.rollback()
        output = exc.to_envelope()
        raise
    except Exception:
        await db.rollback()
        raise
    finally:
        await write_operation_audit(
            db,
            tool_id=tool_id,
            operation_id=operation_id,
            payload=body.payload,
            output=output,
            success=success,
        )
