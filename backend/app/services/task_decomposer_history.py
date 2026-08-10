"""CRUD for Task Decomposer analysis history (unit-of-work: no commits here)."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TaskAnalysisHistory


async def create_history(
    db: AsyncSession,
    raw_task: str,
    context: str,
    task_type: str,
    model_name: str,
    risk_hints: list[str] | None,
    risk_level: str,
    structured_output: dict,
) -> TaskAnalysisHistory:
    record = TaskAnalysisHistory(
        raw_task=raw_task,
        context=context,
        task_type=task_type,
        model_name=model_name,
        risk_hints=risk_hints if risk_hints else None,
        risk_level=risk_level,
        structured_output=structured_output,
    )
    db.add(record)
    await db.flush()
    return record


async def list_history(
    db: AsyncSession,
    task_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TaskAnalysisHistory]:
    query = select(TaskAnalysisHistory).order_by(TaskAnalysisHistory.created_at.desc())
    if task_type:
        query = query.where(TaskAnalysisHistory.task_type == task_type)
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def count_history(
    db: AsyncSession, task_type: str | None = None
) -> int:
    query = select(func.count()).select_from(TaskAnalysisHistory)
    if task_type:
        query = query.where(TaskAnalysisHistory.task_type == task_type)
    result = await db.execute(query)
    return int(result.scalar_one())


async def get_history(db: AsyncSession, record_id: str) -> TaskAnalysisHistory | None:
    result = await db.execute(
        select(TaskAnalysisHistory).where(TaskAnalysisHistory.id == record_id)
    )
    return result.scalar_one_or_none()


async def delete_history(db: AsyncSession, record_id: str) -> bool:
    record = await get_history(db, record_id)
    if record is None:
        return False
    await db.delete(record)
    return True


async def prune_history(db: AsyncSession, max_count: int) -> int:
    """Delete the oldest analyses once history exceeds ``max_count``.

    Mirrors the audit-log and chat-message retention so the Task Decomposer
    table can't grow without bound on a long-lived deployment (every
    ``analyze_task`` would otherwise add a row forever). Returns how many rows
    were deleted (0 when under the cap or the cap is disabled). Call after
    inserting the new record, before the caller commits.
    """
    if max_count <= 0:
        return 0
    count = await db.scalar(
        select(func.count()).select_from(TaskAnalysisHistory)
    )
    if count <= max_count:
        return 0
    excess = count - max_count
    result = await db.execute(
        select(TaskAnalysisHistory.id)
        .order_by(TaskAnalysisHistory.created_at.asc())
        .limit(excess)
    )
    ids = [row for (row,) in result.all()]
    if not ids:
        return 0
    await db.execute(delete(TaskAnalysisHistory).where(TaskAnalysisHistory.id.in_(ids)))
    return len(ids)
