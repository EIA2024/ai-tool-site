"""Practice-record CRUD (unit-of-work: no commits here)."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.tool_plugins.code_agent_flow_viz.models import AgentPracticeRecord


async def create_record(
    db: AsyncSession,
    stage_key: str,
    user_input: str,
    agent_output: str,
    feedback: str,
    next_steps: str,
) -> tuple[AgentPracticeRecord, bool]:
    """Create a practice record, returning the existing one if the content is a duplicate.

    The unique ``content_hash`` column is the source of truth; a concurrent
    duplicate insert surfaces as an IntegrityError and is resolved here, so
    callers never see a 500 for a duplicate.
    """
    content_hash = AgentPracticeRecord.compute_hash(
        stage_key, user_input, agent_output, feedback, next_steps
    )

    record = AgentPracticeRecord(
        stage_key=stage_key,
        user_input=user_input,
        agent_output=agent_output,
        feedback=feedback,
        next_steps=next_steps,
        content_hash=content_hash,
    )
    db.add(record)
    try:
        await db.flush()
        return record, True
    except IntegrityError:
        await db.rollback()
        existing = await get_by_hash(db, content_hash)
        return existing, False


async def import_records(
    db: AsyncSession, records: list[dict]
) -> tuple[int, int]:
    """Bulk-import practice records, deduping by content hash.

    Returns ``(imported, skipped)``. Each record is inserted inside its own
    SQLAlchemy savepoint, so a duplicate (or otherwise failing) insert rolls
    back only that record — never the records imported before it in the same
    batch. This is the batch equivalent of :func:`create_record`, which calls
    ``db.rollback()`` on IntegrityError and would otherwise wipe the whole
    transaction. The caller still owns the transaction and commits once.

    ``records`` is a list of dicts with ``stage_key`` / ``user_input`` /
    ``agent_output`` / ``feedback`` / ``next_steps`` (validated by the caller);
    values are coerced to ``str`` here for a single code path.
    """
    imported = 0
    skipped = 0
    for rec in records:
        stage_key = str(rec.get("stage_key") or "")
        user_input = str(rec.get("user_input") or "")
        agent_output = str(rec.get("agent_output") or "")
        feedback = str(rec.get("feedback") or "")
        next_steps = str(rec.get("next_steps") or "")

        content_hash = AgentPracticeRecord.compute_hash(
            stage_key, user_input, agent_output, feedback, next_steps
        )
        # Fast path: known duplicate (e.g. re-importing an exported file).
        if await get_by_hash(db, content_hash) is not None:
            skipped += 1
            continue

        try:
            async with db.begin_nested():
                db.add(
                    AgentPracticeRecord(
                        stage_key=stage_key,
                        user_input=user_input,
                        agent_output=agent_output,
                        feedback=feedback,
                        next_steps=next_steps,
                        content_hash=content_hash,
                    )
                )
                await db.flush()
            imported += 1
        except IntegrityError:
            # A concurrent insert won the race between the pre-check and this
            # flush; the savepoint absorbed the constraint failure, so the rest
            # of the batch (and the session) is still healthy.
            skipped += 1
    return imported, skipped


async def get_by_hash(
    db: AsyncSession, content_hash: str
) -> AgentPracticeRecord | None:
    result = await db.execute(
        select(AgentPracticeRecord).where(
            AgentPracticeRecord.content_hash == content_hash
        )
    )
    return result.scalar_one_or_none()


async def list_records(
    db: AsyncSession, limit: int = 200, offset: int = 0
) -> list[AgentPracticeRecord]:
    result = await db.execute(
        select(AgentPracticeRecord)
        .order_by(AgentPracticeRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_records(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(AgentPracticeRecord)
    )
    return int(result.scalar_one())


async def get_record(db: AsyncSession, record_id: str) -> AgentPracticeRecord | None:
    result = await db.execute(
        select(AgentPracticeRecord).where(AgentPracticeRecord.id == record_id)
    )
    return result.scalar_one_or_none()


async def delete_record(db: AsyncSession, record_id: str) -> bool:
    record = await get_record(db, record_id)
    if record is None:
        return False
    await db.delete(record)
    return True
