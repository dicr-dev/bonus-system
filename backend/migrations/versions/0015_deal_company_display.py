"""Store linked Bitrix company on deals.

Revision ID: 0015_deal_company_display
Revises: 0014_task_1c_errors
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_deal_company_display"
down_revision = "0014_task_1c_errors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("company_bitrix_id", sa.Integer(), nullable=True))
    op.add_column("deals", sa.Column("company_name", sa.String(length=500), nullable=True))
    op.create_index("ix_deals_company_bitrix_id", "deals", ["company_bitrix_id"])


def downgrade() -> None:
    op.drop_index("ix_deals_company_bitrix_id", table_name="deals")
    op.drop_column("deals", "company_name")
    op.drop_column("deals", "company_bitrix_id")
