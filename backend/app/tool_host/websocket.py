"""Unified realtime WebSocket operation gateway."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, InternalError, RateLimitError, ValidationError
from app.core.ratelimit import is_allowed
from app.db.session import get_db
from app.tool_host.contracts import RealtimeEvent, ToolContext, Transport
from app.tool_host.discovery import get_registry
from app.tool_host.gateway import client_ip, write_operation_audit
from app.tool_host.runtime import resolve_operation, validate_input, validate_output

logger = logging.getLogger(__name__)
router = APIRouter()
registry = get_registry()


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = websocket.headers.get("origin")
    return not origin or origin.rstrip("/") in settings.cors_origins_list


async def _send_error(
    websocket: WebSocket,
    request_id: str | None,
    error: AppError,
) -> None:
    await websocket.send_json(
        {
            "type": "error",
            "request_id": request_id,
            "data": {"code": error.code, "message": error.message},
        }
    )


def _parse_invoke(raw: str) -> tuple[str, dict[str, Any]]:
    try:
        frame = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValidationError("WebSocket frame must be valid JSON") from exc
    if not isinstance(frame, dict) or frame.get("type") != "invoke":
        raise ValidationError("WebSocket frame type must be 'invoke'")
    request_id = str(frame.get("request_id") or "").strip()
    if not request_id or len(request_id) > 128:
        raise ValidationError("request_id must be 1-128 characters")
    payload = frame.get("payload", {})
    if not isinstance(payload, dict):
        raise ValidationError("payload must be an object")
    return request_id, payload


@router.websocket("/tools/{tool_id}/operations/{operation_id}")
async def realtime_operation(
    websocket: WebSocket,
    tool_id: str,
    operation_id: str,
    db: AsyncSession = Depends(get_db),
):
    if not _origin_allowed(websocket):
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    await websocket.accept()
    try:
        operation = resolve_operation(registry, tool_id, operation_id)
        if operation.transport is not Transport.REALTIME:
            raise ValidationError(
                f"Operation '{operation_id}' requires request-response transport"
            )
    except AppError as exc:
        await _send_error(websocket, None, exc)
        await websocket.close(code=1008, reason=exc.message)
        return

    await websocket.send_json(
        {
            "type": "ready",
            "tool_id": tool_id,
            "operation_id": operation_id,
        }
    )
    ip = client_ip(websocket)

    while True:
        request_id: str | None = None
        payload: dict[str, Any] = {}
        output: Any = None
        success = False
        events = None
        try:
            request_id, payload = _parse_invoke(await websocket.receive_text())
            if not await is_allowed(ip, bucket=f"tool:{tool_id}:{operation_id}"):
                raise RateLimitError()
            input_value = validate_input(operation, payload)
            context = ToolContext(db=db, request_id=request_id, client_ip=ip)
            events = operation.handler(input_value, context)
            saw_result = False
            async for raw_event in events:
                event = RealtimeEvent.model_validate(raw_event)
                if event.request_id != request_id:
                    raise RuntimeError("plugin emitted an event for the wrong request_id")
                if event.type == "result":
                    validate_output(operation, event.data)
                    saw_result = True
                    output = event.data
                await websocket.send_json(event.model_dump(mode="json"))
            if not saw_result:
                raise RuntimeError("realtime plugin completed without a result event")
            await db.commit()
            success = True
        except WebSocketDisconnect:
            await db.rollback()
            break
        except AppError as exc:
            await db.rollback()
            output = exc.to_envelope()
            await _send_error(websocket, request_id, exc)
        except (ConnectionError, RuntimeError) as exc:
            await db.rollback()
            if isinstance(exc, ConnectionError):
                break
            logger.exception("Realtime operation failed: %s.%s", tool_id, operation_id)
            internal = InternalError()
            output = internal.to_envelope()
            await _send_error(websocket, request_id, internal)
        except Exception:
            await db.rollback()
            logger.exception("Realtime operation failed: %s.%s", tool_id, operation_id)
            internal = InternalError()
            output = internal.to_envelope()
            try:
                await _send_error(websocket, request_id, internal)
            except Exception:
                break
        finally:
            if events is not None:
                await events.aclose()
            if request_id is not None:
                await write_operation_audit(
                    db,
                    tool_id=tool_id,
                    operation_id=operation_id,
                    payload=payload,
                    output=output,
                    success=success,
                )
