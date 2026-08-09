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
    # chat_messages.session_id is used in WHERE/join on every chat history
    # read — index it for scale.
    op.create_index(
        "ix_chat_messages_session_id",
        "chat_messages",
        ["session_id"],
    )
    # Normalize legacy "bot" role to "assistant" before adding the CHECK.
    op.execute("UPDATE chat_messages SET role = 'assistant' WHERE role = 'bot'")
    op.create_check_constraint(
        "ck_chat_messages_role",
        "chat_messages",
        "role IN ('user', 'assistant', 'system')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_chat_messages_role", "chat_messages", type_="check")
    op.execute("UPDATE chat_messages SET role = 'bot' WHERE role = 'assistant'")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
