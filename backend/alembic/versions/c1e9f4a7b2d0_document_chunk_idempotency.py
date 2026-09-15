"""enforce document chunk idempotency

Revision ID: c1e9f4a7b2d0
Revises: b7e2d4a91c03
"""
from collections.abc import Sequence

from alembic import op

revision: str = "c1e9f4a7b2d0"
down_revision: str | None = "b7e2d4a91c03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_document_chunks_source_document_index",
        "document_chunks",
        ["source_document_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_document_chunks_source_document_index",
        "document_chunks",
        type_="unique",
    )