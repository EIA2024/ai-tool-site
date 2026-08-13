"""Shared validation and dispatch across the Host–Plugin seam."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import NotFoundError, ValidationError
from app.tool_host.contracts import OperationDefinition, ToolContext, Transport
from app.tool_host.registry import ToolRegistry


def resolve_operation(
    registry: ToolRegistry, tool_id: str, operation_id: str
) -> OperationDefinition:
    plugin = registry.get(tool_id)
    if plugin is None:
        raise NotFoundError(f"Tool '{tool_id}' not found")
    operation = plugin.get_operation(operation_id)
    if operation is None:
        raise NotFoundError(
            f"Operation '{operation_id}' not found for tool '{tool_id}'"
        )
    return operation


def validate_input(operation: OperationDefinition, payload: Any) -> BaseModel:
    try:
        return operation.input_model.model_validate(payload)
    except PydanticValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "payload"
        raise ValidationError(f"{location}: {first['msg']}") from exc


def validate_output(operation: OperationDefinition, value: Any) -> BaseModel:
    try:
        return operation.output_model.model_validate(value)
    except PydanticValidationError as exc:
        raise RuntimeError(
            f"plugin operation '{operation.id}' returned an invalid output"
        ) from exc


async def invoke_request_operation(
    operation: OperationDefinition,
    payload: Any,
    context: ToolContext,
) -> BaseModel:
    if operation.transport is not Transport.REQUEST_RESPONSE:
        raise ValidationError(
            f"Operation '{operation.id}' requires the realtime WebSocket transport"
        )
    input_value = validate_input(operation, payload)
    result = await operation.handler(input_value, context)
    return validate_output(operation, result)
