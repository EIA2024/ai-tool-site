"""harden chat tables: index session_id, constrain role values

Revision ID: 004
Revises: 003
Create Date: 2026-08-10
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize legacy "bot" role to "assistant" before adding the CHECK.
    op.execute("UPDATE chat_messages SET role = 'assistant' WHERE role = 'bot'")
    # Batch mode: chat_messages.session_id is used in WHERE/join on every chat
    # history read — index it for scale. On Postgres batch emits the same DDL
    # as the old direct calls; on SQLite it uses a copy-and-move strategy
    # because SQLite cannot ALTER to add constraints.
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.create_check_constraint(
            "ck_chat_messages_role",
            "role IN ('user', 'assistant', 'system')",
        )
        batch_op.create_index(
            "ix_chat_messages_session_id",
            ["session_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_constraint("ck_chat_messages_role", type_="check")
        batch_op.drop_index("ix_chat_messages_session_id")
    op.execute("UPDATE chat_messages SET role = 'bot' WHERE role = 'assistant'")
