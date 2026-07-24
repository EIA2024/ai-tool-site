"""add agent_practice_records table

Revision ID: 002
Revises: 001
Create Date: 2026-07-25
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_practice_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stage_key", sa.String(20), nullable=False),
        sa.Column("user_input", sa.Text, nullable=False, server_default=""),
        sa.Column("agent_output", sa.Text, nullable=False, server_default=""),
        sa.Column("feedback", sa.Text, nullable=False, server_default=""),
        sa.Column("next_steps", sa.Text, nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_agent_practice_records_content_hash",
        "agent_practice_records",
        ["content_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_practice_records_content_hash", table_name="agent_practice_records")
    op.drop_table("agent_practice_records")
