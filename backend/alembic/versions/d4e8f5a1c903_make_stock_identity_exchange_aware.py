"""make stock identity exchange aware without removing existing data

Revision ID: d4e8f5a1c903
Revises: c3a9e274bf10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e8f5a1c903"
down_revision: Union[str, Sequence[str], None] = "c3a9e274bf10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing cached listings with an unknown exchange remain valid as the
    # empty-exchange legacy listing; no stock, transaction, or holding is lost.
    op.execute("UPDATE stocks SET exchange = '' WHERE exchange IS NULL")
    op.drop_index("ix_stocks_symbol", table_name="stocks")
    op.drop_constraint("stocks_symbol_key", "stocks", type_="unique")
    op.alter_column("stocks", "exchange", existing_type=sa.String(length=64), nullable=False)
    op.create_unique_constraint("uq_stocks_symbol_exchange", "stocks", ["symbol", "exchange"])
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stocks_symbol", table_name="stocks")
    op.drop_constraint("uq_stocks_symbol_exchange", "stocks", type_="unique")
    op.alter_column("stocks", "exchange", existing_type=sa.String(length=64), nullable=True)
    op.create_unique_constraint("stocks_symbol_key", "stocks", ["symbol"])
    op.create_index("ix_stocks_symbol", "stocks", ["symbol"], unique=True)
