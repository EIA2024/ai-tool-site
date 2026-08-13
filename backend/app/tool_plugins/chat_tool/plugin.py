"""Realtime chat plugin with Host-managed transport and transactions."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.services.llm import (
    ProviderError,
    chat_completion_stream,
    get_default_model,
    get_models,
    is_model_supported,
)
from app.tool_host.contracts import (
    OperationDefinition,
    RealtimeEvent,
    ToolContext,
    ToolPlugin,
    ToolUi,
    Transport,
    UiKind,
)
from app.tool_plugins.chat_tool.models import ChatMessage, ChatSession
from app.tool_plugins.chat_tool.repository import (
    add_message,
    auto_title_on_first_message,
    create_session,
    delete_session,
    get_context_messages,
    get_messages,
    get_recent_sessions,
    get_session,
    prune_session_messages,
    touch_session,
)

logger = logging.getLogger(__name__)

_CONTEXT_LIMIT = 20
_MAX_CONTEXT_FETCH = 200
_CONTEXT_CHAR_BUDGET = 24_000
_SYSTEM_PROMPT = (
    "你是一个友好的 AI 助手，运行在用户的 AI 工具站里，通过 WebSocket 聊天。"
    "用中文回答，简洁准确，除代码外不需要 Markdown 排版。"
)


class EmptyInput(BaseModel):
    pass


class SessionData(BaseModel):
    id: str
    title: str
    tool_id: str | None
    created_at: str | None
    updated_at: str | None


class MessageData(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: str | None


class ListSessionsInput(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)


class ListSessionsOutput(BaseModel):
    sessions: list[SessionData]


class CreateSessionInput(BaseModel):
    title: str = Field(default="New Chat", max_length=255)


class SessionOutput(BaseModel):
    session: SessionData


class SessionIdInput(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)


class DeleteSessionOutput(BaseModel):
    deleted: bool


class ListMessagesInput(SessionIdInput):
    limit: int = Field(default=200, ge=1, le=1000)
    offset: int = Field(default=0, ge=0, le=1_000_000)


class ListMessagesOutput(BaseModel):
    messages: list[MessageData]


class SendMessageInput(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    content: str = Field(min_length=1, max_length=10_000)
    model: str = Field(default="", max_length=64)
    # Transient per-session key (like Task Decomposer's session_api_key): when
    # set it is used instead of the server key for this one message.
    session_api_key: str = Field(default="", max_length=256)

    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value

    @field_validator("session_api_key", mode="before")
    @classmethod
    def _coerce_key(cls, value) -> str:
        return str(value or "")


class SendMessageOutput(BaseModel):
    session_id: str
    message: MessageData


def _session_data(session: ChatSession) -> SessionData:
    return SessionData(
        id=session.id,
        title=session.title,
        tool_id=session.tool_id,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
    )


def _message_data(message: ChatMessage) -> MessageData:
    return MessageData(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at.isoformat() if message.created_at else None,
    )


async def list_sessions(
    payload: ListSessionsInput, context: ToolContext
) -> ListSessionsOutput:
    sessions = await get_recent_sessions(context.db, limit=payload.limit)
    return ListSessionsOutput(sessions=[_session_data(session) for session in sessions])


async def new_session(
    payload: CreateSessionInput, context: ToolContext
) -> SessionOutput:
    session = await create_session(
        context.db,
        title=payload.title.strip() or "New Chat",
        tool_id="chat_tool",
    )
    return SessionOutput(session=_session_data(session))


async def get_one_session(
    payload: SessionIdInput, context: ToolContext
) -> SessionOutput:
    session = await get_session(context.db, payload.session_id)
    if session is None:
        raise NotFoundError("Session not found")
    return SessionOutput(session=_session_data(session))


async def remove_session(
    payload: SessionIdInput, context: ToolContext
) -> DeleteSessionOutput:
    if not await delete_session(context.db, payload.session_id):
        raise NotFoundError("Session not found")
    return DeleteSessionOutput(deleted=True)


async def list_session_messages(
    payload: ListMessagesInput, context: ToolContext
) -> ListMessagesOutput:
    if await get_session(context.db, payload.session_id) is None:
        raise NotFoundError("Session not found")
    messages = await get_messages(
        context.db,
        payload.session_id,
        limit=payload.limit,
        offset=payload.offset,
    )
    return ListMessagesOutput(messages=[_message_data(message) for message in messages])


def _map_role(role: str) -> str:
    return role if role in ("user", "assistant", "system") else "user"


def _trim_context(
    messages: list[dict[str, str]], budget: int = _CONTEXT_CHAR_BUDGET
) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    used = 0
    for message in reversed(messages):
        cost = len(message["content"]) + 32
        if used + cost > budget and kept:
            break
        kept.append(message)
        used += cost
    return list(reversed(kept))


async def send_message(payload: SendMessageInput, context: ToolContext):
    session = None
    if payload.session_id:
        session = await get_session(context.db, payload.session_id)
    if session is None:
        session = await create_session(
            context.db,
            title="WebSocket Chat",
            tool_id="chat_tool",
        )

    model = payload.model or get_default_model()
    if not is_model_supported(model):
        raise ValidationError(
            f"不支持的模型 '{model}'。可选：{', '.join(get_models())}"
        )

    try:
        history = await get_context_messages(
            context.db,
            session.id,
            limit=_MAX_CONTEXT_FETCH,
        )
    except Exception:
        logger.warning(
            "Failed to load chat context for session %s",
            session.id,
            exc_info=True,
        )
        history = []
    model_context = [
        {"role": _map_role(message.role), "content": message.content}
        for message in history[-_CONTEXT_LIMIT:]
    ]
    model_context = _trim_context(model_context)
    model_context.append({"role": "user", "content": payload.content})

    await auto_title_on_first_message(context.db, session, payload.content)
    await add_message(context.db, session.id, "user", payload.content)
    await prune_session_messages(
        context.db,
        session.id,
        settings.chat_max_messages_per_session,
    )
    await touch_session(context.db, session.id)

    request_id = context.request_id or ""
    yield RealtimeEvent(
        type="progress",
        request_id=request_id,
        data={"stage": "typing", "session_id": session.id},
    )

    stream = chat_completion_stream(
        [{"role": "system", "content": _SYSTEM_PROMPT}] + model_context,
        model,
        max_tokens=settings.chat_max_tokens,
        thinking=settings.chat_thinking,
        reasoning_effort=(
            settings.chat_reasoning_effort or None
            if settings.chat_thinking
            else None
        ),
        api_key=payload.session_api_key,
    )
    chunks: list[str] = []
    reply = ""
    try:
        async for delta in stream:
            chunks.append(delta)
            yield RealtimeEvent(
                type="delta",
                request_id=request_id,
                data={"content": delta},
            )
        reply = "".join(chunks)
    except ProviderError as exc:
        reply = f"（AI 调用失败：{exc}）"
        logger.warning("Chat AI failure for session %s: %s", session.id, exc)
    except Exception as exc:
        reply = "（AI 调用失败：模型输出异常）"
        logger.warning(
            "Unexpected error streaming reply for session %s: %s",
            session.id,
            exc,
            exc_info=True,
        )
    finally:
        await stream.aclose()

    if not reply.strip():
        reply = "（AI 调用失败：模型返回了空回复）"

    message = await add_message(context.db, session.id, "assistant", reply)
    await prune_session_messages(
        context.db,
        session.id,
        settings.chat_max_messages_per_session,
    )
    await touch_session(context.db, session.id)
    output = SendMessageOutput(
        session_id=session.id,
        message=_message_data(message),
    )
    yield RealtimeEvent(
        type="result",
        request_id=request_id,
        data=output.model_dump(mode="json"),
    )


plugin = ToolPlugin(
    id="chat_tool",
    version="1.0.0",
    name="Chat Tool",
    description="Realtime multi-turn chat with streamed AI responses",
    ui=ToolUi(kind=UiKind.CUSTOM),
    operations=(
        OperationDefinition(
            "list_sessions",
            Transport.REQUEST_RESPONSE,
            ListSessionsInput,
            ListSessionsOutput,
            list_sessions,
        ),
        OperationDefinition(
            "create_session",
            Transport.REQUEST_RESPONSE,
            CreateSessionInput,
            SessionOutput,
            new_session,
        ),
        OperationDefinition(
            "get_session",
            Transport.REQUEST_RESPONSE,
            SessionIdInput,
            SessionOutput,
            get_one_session,
        ),
        OperationDefinition(
            "delete_session",
            Transport.REQUEST_RESPONSE,
            SessionIdInput,
            DeleteSessionOutput,
            remove_session,
        ),
        OperationDefinition(
            "list_messages",
            Transport.REQUEST_RESPONSE,
            ListMessagesInput,
            ListMessagesOutput,
            list_session_messages,
        ),
        OperationDefinition(
            "send_message",
            Transport.REALTIME,
            SendMessageInput,
            SendMessageOutput,
            send_message,
        ),
    ),
)
