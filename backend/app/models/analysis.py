import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class TaskAnalysisHistory(Base):
    """A saved analysis record for the Task Decomposer tool."""

    __tablename__ = "task_analysis_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    raw_task: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_hints: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    structured_output: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
