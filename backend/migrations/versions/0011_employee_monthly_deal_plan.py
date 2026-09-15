"""Add employee monthly deal plan.

Revision ID: 0011_employee_monthly_deal_plan
Revises: 0010_onboarding_template
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_employee_monthly_deal_plan"
down_revision = "0010_onboarding_template"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_monthly_deal_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("month", "employee_id", "deal_id", name="uq_employee_monthly_deal_plan"),
    )
    op.create_index("ix_employee_monthly_deal_plans_month", "employee_monthly_deal_plans", ["month"])
    op.create_index("ix_employee_monthly_deal_plans_employee_id", "employee_monthly_deal_plans", ["employee_id"])
    op.create_index("ix_employee_monthly_deal_plans_deal_id", "employee_monthly_deal_plans", ["deal_id"])


def downgrade() -> None:
    op.drop_table("employee_monthly_deal_plans")
