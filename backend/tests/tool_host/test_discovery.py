"""Plugin discovery and manifest validation tests.

The Host must reject malformed plugins at startup (duplicate tool ids, invalid
operation ids, handler/transport mismatches, duplicate operations) and discover
the four built-in plugins successfully.
"""

import pytest
from pydantic import BaseModel

from app.tool_host.contracts import (
    OperationDefinition,
    RealtimeEvent,
    ToolContext,
    ToolPlugin,
    ToolUi,
    Transport,
    UiKind,
)
from app.tool_host.discovery import discover_plugins
from app.tool_host.registry import ToolRegistry


class _In(BaseModel):
    input: str = ""


class _Out(BaseModel):
    echo: str = ""


async def _echo(payload: _In, context: ToolContext) -> _Out:
    return _Out(echo=payload.input)


async def _stream(payload: _In, context: ToolContext):
    yield RealtimeEvent(type="result", request_id="r", data={"echo": "x"})


def _operation(op_id: str, transport: Transport = Transport.REQUEST_RESPONSE):
    handler = _echo if transport is Transport.REQUEST_RESPONSE else _stream
    return OperationDefinition(op_id, transport, _In, _Out, handler)


def _plugin(tool_id="my_tool", operations=None):
    return ToolPlugin(
        id=tool_id,
        version="1.0.0",
        name="My Tool",
        description="A test plugin",
        ui=ToolUi(kind=UiKind.SCHEMA),
        operations=tuple(operations or [_operation("op")]),
    )


def test_discover_builtin_plugins():
    registry = discover_plugins()
    assert len(registry) == 4
    assert [m.id for m in registry.manifests()] == [
        "blank_tool",
        "chat_tool",
        "code_agent_flow_viz",
        "task_decomposer",
    ]


def test_discover_empty_package_raises():
    """A package with no plugin subpackages fails fast (no silent empty site)."""
    with pytest.raises(RuntimeError, match="no tool plugins"):
        discover_plugins("app.services")


def test_registry_rejects_duplicate_tool_id():
    registry = ToolRegistry()
    registry.register(_plugin("dup_tool"))
    with pytest.raises(ValueError, match="duplicate tool id"):
        registry.register(_plugin("dup_tool"))


def test_registry_len_and_get():
    registry = ToolRegistry()
    registry.register(_plugin("a_tool"))
    assert len(registry) == 1
    assert registry.get("a_tool") is not None
    assert registry.get("missing") is None


def test_operation_rejects_invalid_id():
    with pytest.raises(ValueError):
        OperationDefinition("bad-id", Transport.REQUEST_RESPONSE, _In, _Out, _echo)


def test_request_response_requires_coroutine_handler():
    with pytest.raises(TypeError):
        OperationDefinition("op", Transport.REQUEST_RESPONSE, _In, _Out, _stream)


def test_realtime_requires_async_generator_handler():
    with pytest.raises(TypeError):
        OperationDefinition("op", Transport.REALTIME, _In, _Out, _echo)


def test_plugin_rejects_duplicate_operations():
    with pytest.raises(ValueError):
        _plugin(operations=[_operation("op"), _operation("op")])


def test_plugin_manifest_shape():
    manifest = _plugin("shape_tool").manifest()
    assert manifest.contract_version == "1"
    assert manifest.id == "shape_tool"
    assert manifest.ui.kind == UiKind.SCHEMA
    operation = manifest.operations[0]
    assert operation.id == "op"
    assert operation.transport == Transport.REQUEST_RESPONSE
    # The input/output JSON Schema is derived from the Pydantic models.
    assert operation.input_schema["type"] == "object"
    assert operation.output_schema["properties"]["echo"]["type"] == "string"
