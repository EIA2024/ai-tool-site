from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentPracticeRecord


async def create_record(
    db: AsyncSession,
    stage_key: str,
    user_input: str,
    agent_output: str,
    feedback: str,
    next_steps: str,
) -> tuple[AgentPracticeRecord, bool]:
    """Create a practice record or return existing one if duplicate.

    Returns:
        Tuple of (record, created), where created is True if a new row was inserted.
    """
    content_hash = AgentPracticeRecord.compute_hash(
        stage_key, user_input, agent_output, feedback, next_steps
    )

    # Check for existing duplicate
    existing = await db.execute(
        select(AgentPracticeRecord).where(
            AgentPracticeRecord.content_hash == content_hash
        )
    )
    existing_record = existing.scalar_one_or_none()
    if existing_record is not None:
        return existing_record, False

    record = AgentPracticeRecord(
        stage_key=stage_key,
        user_input=user_input,
        agent_output=agent_output,
        feedback=feedback,
        next_steps=next_steps,
        content_hash=content_hash,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record, True


async def list_records(db: AsyncSession) -> list[AgentPracticeRecord]:
    result = await db.execute(
        select(AgentPracticeRecord).order_by(AgentPracticeRecord.created_at.desc())
    )
    return list(result.scalars().all())


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
    await db.commit()
    return True
