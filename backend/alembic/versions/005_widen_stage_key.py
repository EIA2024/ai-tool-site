"""widen agent_practice_records.stage_key to match the tool's 64-char cap

Revision ID: 005
Revises: 004
Create Date: 2026-08-10
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The Code Agent Flow Viz tool accepts stage_key up to 64 chars, but the
    # column was VARCHAR(20) — Postgres enforces the length, so any key longer
    # than 20 chars passed tool validation and then 500'd with a DataError.
    # Batch mode so the same script also runs on SQLite (copy-and-move).
    with op.batch_alter_table("agent_practice_records") as batch_op:
        batch_op.alter_column(
            "stage_key",
            existing_type=sa.String(20),
            type_=sa.String(64),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_practice_records") as batch_op:
        batch_op.alter_column(
            "stage_key",
            existing_type=sa.String(64),
            type_=sa.String(20),
            existing_nullable=False,
        )
