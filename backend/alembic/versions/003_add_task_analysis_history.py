"""add task_analysis_history table

Revision ID: 003
Revises: 002
Create Date: 2026-07-25
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_analysis_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("raw_task", sa.Text, nullable=False),
        sa.Column("context", sa.Text, nullable=False, server_default=""),
        sa.Column("task_type", sa.String(20), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("risk_hints", sa.JSON, nullable=True),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("structured_output", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_task_analysis_history_created_at",
        "task_analysis_history",
        ["created_at"],
    )
    op.create_index(
        "ix_task_analysis_history_task_type",
        "task_analysis_history",
        ["task_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_analysis_history_task_type", table_name="task_analysis_history")
    op.drop_index("ix_task_analysis_history_created_at", table_name="task_analysis_history")
    op.drop_table("task_analysis_history")
