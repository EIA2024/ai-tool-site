"""Runtime dispatch and schema-validation tests.

The Host runtime is the single seam every operation crosses: it resolves the
tool/operation, validates the input payload against the operation's Pydantic
model, runs the handler, and validates the output. These tests pin that
dispatch and the typed errors it raises.
"""

import pytest
from pydantic import BaseModel, Field

from app.core.errors import NotFoundError, ValidationError
from app.tool_host.contracts import (
    OperationDefinition,
    RealtimeEvent,
    ToolContext,
    Transport,
)
from app.tool_host.discovery import get_registry
from app.tool_host.runtime import (
    invoke_request_operation,
    resolve_operation,
    validate_input,
    validate_output,
)


class _In(BaseModel):
    input: str = Field(default="", max_length=10)


class _Out(BaseModel):
    echo: str


async def _echo(payload: _In, context: ToolContext) -> _Out:
    return _Out(echo=payload.input)


async def _stream(payload: _In, context: ToolContext):
    yield RealtimeEvent(type="result", request_id="r", data={"echo": "x"})


def _request_operation(op_id="op"):
    return OperationDefinition(op_id, Transport.REQUEST_RESPONSE, _In, _Out, _echo)


def test_resolve_operation_known():
    registry = get_registry()
    op = resolve_operation(registry, "blank_tool", "echo")
    assert op.id == "echo"


def test_resolve_operation_unknown_tool():
    with pytest.raises(NotFoundError):
        resolve_operation(get_registry(), "missing", "echo")


def test_resolve_operation_unknown_operation():
    with pytest.raises(NotFoundError):
        resolve_operation(get_registry(), "blank_tool", "missing")


def test_validate_input_valid():
    model = validate_input(_request_operation(), {"input": "hi"})
    assert isinstance(model, _In)
    assert model.input == "hi"


def test_validate_input_invalid_location_and_message():
    with pytest.raises(ValidationError) as excinfo:
        validate_input(_request_operation(), {"input": "x" * 4001})
    assert excinfo.value.code == "VALIDATION_ERROR"
    # The error reports the offending field and the pydantic reason.
    assert "input" in str(excinfo.value)


def test_validate_output_valid():
    model = validate_output(_request_operation(), {"echo": "hi"})
    assert isinstance(model, _Out)


def test_validate_output_invalid_raises_runtime_error():
    with pytest.raises(RuntimeError):
        validate_output(_request_operation(), {"wrong": True})


@pytest.mark.asyncio
async def test_invoke_request_operation_dispatches(db):
    result = await invoke_request_operation(
        _request_operation(), {"input": "hi"}, ToolContext(db=db)
    )
    assert result.echo == "hi"


@pytest.mark.asyncio
async def test_invoke_request_operation_rejects_realtime(db):
    realtime = OperationDefinition("op", Transport.REALTIME, _In, _Out, _stream)
    with pytest.raises(ValidationError):
        await invoke_request_operation(realtime, {"input": "x"}, ToolContext(db=db))
