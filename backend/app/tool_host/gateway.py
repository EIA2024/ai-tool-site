"""Shared gateway concerns for REST and WebSocket tool operations."""

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redact import redact
from app.services.audit import log_tool_call, prune_tool_calls

logger = logging.getLogger(__name__)
_AUDIT_CAP = 100_000


def client_ip(connection: Any) -> str:
    if settings.trust_proxy_headers:
        forwarded = connection.headers.get("x-forwarded-for")
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    client = getattr(connection, "client", None)
    return client.host if client else "unknown"


def serialize_for_audit(value: Any) -> str:
    try:
        text = json.dumps(redact(value), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return text[:_AUDIT_CAP]


async def write_operation_audit(
    db: AsyncSession,
    *,
    tool_id: str,
    operation_id: str,
    payload: Any,
    output: Any,
    success: bool,
) -> None:
    try:
        await log_tool_call(
            db,
            tool_id,
            serialize_for_audit({"operation": operation_id, "payload": payload}),
            serialize_for_audit(output) if output is not None else None,
            success,
        )
        await prune_tool_calls(db, settings.audit_max_records)
        await db.commit()
    except Exception:
        logger.warning(
            "Failed to write audit record for %s.%s",
            tool_id,
            operation_id,
            exc_info=True,
        )
        await db.rollback()
