"""add Markdown content to source documents

Revision ID: b7e2d4a91c03
Revises: 8c4f9db2a1e7
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e2d4a91c03"
down_revision: str | None = "8c4f9db2a1e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("markdown_content", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_documents", "markdown_content")