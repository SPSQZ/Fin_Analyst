"""add chat message parts and sequence

Revision ID: 8c4f9db2a1e7
Revises: 6f0d666fe150
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8c4f9db2a1e7"
down_revision: str | None = "6f0d666fe150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("sequence", sa.Integer(), nullable=True))
    op.execute(
        """
        WITH numbered AS (
            SELECT id, row_number() OVER (
                PARTITION BY thread_id ORDER BY created_at, id
            ) - 1 AS sequence_number
            FROM chat_messages
        )
        UPDATE chat_messages AS messages
        SET sequence = numbered.sequence_number
        FROM numbered
        WHERE messages.id = numbered.id
        """
    )
    op.alter_column("chat_messages", "sequence", nullable=False)
    op.add_column(
        "chat_messages",
        sa.Column("parts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "parts")
    op.drop_column("chat_messages", "sequence")