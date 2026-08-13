"""Versioned Host–Plugin contract for AI Tool Dock."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

CONTRACT_VERSION = "1"
_ID_PATTERN = r"^[a-z][a-z0-9_]*$"


class Transport(str, Enum):
    REQUEST_RESPONSE = "request-response"
    REALTIME = "realtime"


class UiKind(str, Enum):
    SCHEMA = "schema"
    CUSTOM = "custom"


class UiLayout(str, Enum):
    STANDARD = "standard"
    FULLSCREEN = "fullscreen"


class ToolUi(BaseModel):
    kind: UiKind
    layout: UiLayout = UiLayout.STANDARD


class OperationManifest(BaseModel):
    id: str = Field(pattern=_ID_PATTERN)
    transport: Transport
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ToolManifest(BaseModel):
    contract_version: Literal["1"] = CONTRACT_VERSION
    id: str = Field(pattern=_ID_PATTERN)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    ui: ToolUi
    operations: list[OperationManifest] = Field(min_length=1)

    @model_validator(mode="after")
    def _operation_ids_are_unique(self) -> "ToolManifest":
        operation_ids = [operation.id for operation in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError(f"tool '{self.id}' declares duplicate operation ids")
        return self


class ToolContext(BaseModel):
    """Host-owned dependencies supplied to one plugin operation."""

    model_config = {"arbitrary_types_allowed": True}

    db: AsyncSession
    request_id: str | None = None
    client_ip: str = "unknown"


class RealtimeEvent(BaseModel):
    type: Literal["progress", "delta", "result", "error"]
    request_id: str
    data: dict[str, Any] = Field(default_factory=dict)


RequestHandler = Callable[[BaseModel, ToolContext], Awaitable[BaseModel | dict[str, Any]]]
RealtimeHandler = Callable[[BaseModel, ToolContext], AsyncIterator[RealtimeEvent]]


@dataclass(frozen=True)
class OperationDefinition:
    id: str
    transport: Transport
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: RequestHandler | RealtimeHandler

    def __post_init__(self) -> None:
        if not self.id or not self.id.replace("_", "a").isalnum() or not self.id[0].isalpha():
            raise ValueError(f"invalid operation id: {self.id!r}")
        is_async_generator = inspect.isasyncgenfunction(self.handler)
        is_coroutine = inspect.iscoroutinefunction(self.handler)
        if self.transport is Transport.REQUEST_RESPONSE and not is_coroutine:
            raise TypeError(
                f"request-response operation '{self.id}' requires an async handler"
            )
        if self.transport is Transport.REALTIME and not is_async_generator:
            raise TypeError(
                f"realtime operation '{self.id}' requires an async-generator handler"
            )

    def manifest(self) -> OperationManifest:
        return OperationManifest(
            id=self.id,
            transport=self.transport,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
        )


@dataclass(frozen=True)
class ToolPlugin:
    id: str
    version: str
    name: str
    description: str
    ui: ToolUi
    operations: tuple[OperationDefinition, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Build once during registration so malformed plugins fail immediately.
        self.manifest()

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            id=self.id,
            version=self.version,
            name=self.name,
            description=self.description,
            ui=self.ui,
            operations=[operation.manifest() for operation in self.operations],
        )

    def get_operation(self, operation_id: str) -> OperationDefinition | None:
        return next(
            (operation for operation in self.operations if operation.id == operation_id),
            None,
        )
