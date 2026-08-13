"""Hidden schema-rendered example plugin."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.tool_host.contracts import (
    OperationDefinition,
    ToolContext,
    ToolPlugin,
    ToolUi,
    Transport,
    UiKind,
)


class EchoInput(BaseModel):
    input: str = Field(default="", max_length=4000, description="Text to echo")

    @field_validator("input", mode="before")
    @classmethod
    def _coerce_input(cls, value: Any) -> str:
        return str(value or "")


class EchoOutput(BaseModel):
    echo: str
    message: str


async def echo(payload: EchoInput, context: ToolContext) -> EchoOutput:
    return EchoOutput(
        echo=payload.input,
        message="Blank tool response — ready for AI integration.",
    )


plugin = ToolPlugin(
    id="blank_tool",
    version="1.0.0",
    name="Blank Tool",
    description="A schema-rendered request-response plugin template",
    ui=ToolUi(kind=UiKind.SCHEMA),
    operations=(
        OperationDefinition(
            id="echo",
            transport=Transport.REQUEST_RESPONSE,
            input_model=EchoInput,
            output_model=EchoOutput,
            handler=echo,
        ),
    ),
)
