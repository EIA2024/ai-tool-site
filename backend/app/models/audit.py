import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class ToolCallRecord(Base):
    """Audit log entry: one row per tool invocation.

    Populated automatically by the API layer on every
    ``POST /api/tools/{tool_id}/invoke`` so operators can see usage,
    failure rates, and raw inputs/outputs.
    """

    __tablename__ = "tool_call_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tool_id: Mapped[str] = mapped_column(String(100), nullable=False)
    input_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
