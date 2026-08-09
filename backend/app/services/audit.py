"""Tool-call audit log (unit-of-work: no commits here)."""

from sqlalchemy import func, select
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
