import hashlib
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class AgentPracticeRecord(Base):
    """A single practice record for the Code Agent Flow Visualizer tool."""

    __tablename__ = "agent_practice_records"
    # The unique index on content_hash matches migration 002 (dedup source of
    # truth); declaring it here keeps `alembic check` drift-free.
    __table_args__ = (
        Index("ix_agent_practice_records_content_hash", "content_hash", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    stage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    user_input: Mapped[str] = mapped_column(Text, default="")
    agent_output: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text, default="")
    next_steps: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    @staticmethod
    def compute_hash(
        stage_key: str,
        user_input: str,
        agent_output: str,
        feedback: str,
        next_steps: str,
    ) -> str:
        raw = f"{stage_key}|{user_input}|{agent_output}|{feedback}|{next_steps}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
