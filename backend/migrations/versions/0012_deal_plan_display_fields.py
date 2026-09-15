"""Add deal display fields for employee plans.

Revision ID: 0012_deal_plan_display_fields
Revises: 0011_employee_monthly_deal_plan
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_deal_plan_display_fields"
down_revision = "0011_employee_monthly_deal_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("stage_title", sa.String(length=255), nullable=True))
    op.add_column("deals", sa.Column("salesperson_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "salesperson_name")
    op.drop_column("deals", "stage_title")
