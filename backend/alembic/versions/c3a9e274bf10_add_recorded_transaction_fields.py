"""add fields for recorded portfolio transactions

Revision ID: c3a9e274bf10
Revises: b84d3c9e71a2
Create Date: 2026-08-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a9e274bf10"
down_revision: Union[str, Sequence[str], None] = "b84d3c9e71a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("fees", sa.Numeric(precision=18, scale=2), server_default="0", nullable=False))
    op.add_column("transactions", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("transactions", sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_index("ix_transactions_executed_at", "transactions", ["executed_at"])
    op.alter_column("transactions", "fees", server_default=None)
    op.alter_column("transactions", "executed_at", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_transactions_executed_at", table_name="transactions")
    op.drop_column("transactions", "executed_at")
    op.drop_column("transactions", "notes")
    op.drop_column("transactions", "fees")
