"""Tool-call audit log (unit-of-work: no commits here)."""

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolCallRecord


async def log_tool_call(
    db: AsyncSession,
    tool_id: str,
    input_data: str | None,
    output_data: str | None,
    success: bool,
) -> ToolCallRecord:
    record = ToolCallRecord(
        tool_id=tool_id,
        input_data=input_data,
        output_data=output_data,
        success=success,
    )
    db.add(record)
    await db.flush()
    return record


async def list_tool_calls(
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    tool_id: str | None = None,
    success: bool | None = None,
) -> list[ToolCallRecord]:
    query = select(ToolCallRecord).order_by(ToolCallRecord.created_at.desc())
    if tool_id:
        query = query.where(ToolCallRecord.tool_id == tool_id)
    if success is not None:
        query = query.where(ToolCallRecord.success == success)
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def count_tool_calls(
    db: AsyncSession,
    tool_id: str | None = None,
    success: bool | None = None,
) -> int:
    query = select(func.count()).select_from(ToolCallRecord)
    if tool_id:
        query = query.where(ToolCallRecord.tool_id == tool_id)
    if success is not None:
        query = query.where(ToolCallRecord.success == success)
    result = await db.execute(query)
    return int(result.scalar_one())


async def summarize_tool_calls(db: AsyncSession) -> list[dict]:
    """Per-tool call/failure counts for the usage dashboard."""
    result = await db.execute(
        select(
            ToolCallRecord.tool_id,
            func.count().label("calls"),
            func.sum(
                case((ToolCallRecord.success.is_(False), 1), else_=0)
            ).label("failures"),
        ).group_by(ToolCallRecord.tool_id)
    )
    return [
        {
            "tool_id": tool_id,
            "calls": int(calls),
            "failures": int(failures or 0),
        }
        for tool_id, calls, failures in result.all()
    ]


async def prune_tool_calls(db: AsyncSession, max_count: int) -> int:
    """Delete the oldest audit rows once the table exceeds ``max_count``.

    Bounds the audit table for long-lived deployments (mirrors
    ``prune_session_messages``). Returns how many rows were deleted (0 when
    under the cap or the cap is disabled). Call after logging, before commit.
    """
    if max_count <= 0:
        return 0
    count = await db.scalar(select(func.count()).select_from(ToolCallRecord))
    if count <= max_count:
        return 0
    excess = count - max_count
    result = await db.execute(
        select(ToolCallRecord.id)
        .order_by(ToolCallRecord.created_at.asc())
        .limit(excess)
    )
    ids = [row for (row,) in result.all()]
    if not ids:
        return 0
    await db.execute(delete(ToolCallRecord).where(ToolCallRecord.id.in_(ids)))
    return len(ids)
