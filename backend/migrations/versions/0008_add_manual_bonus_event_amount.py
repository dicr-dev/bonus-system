"""Add generic deal correction modes and manual bonus adjustments.

Revision ID: 0008_manual_bonus_amount
Revises: 0007_task_sync
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_manual_bonus_amount"
down_revision = "0007_task_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_bonus_events",
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
    )
    op.execute(
        "UPDATE manual_bonus_events "
        "SET amount = 10000 "
        "WHERE event_type = 'cr_start_period_override'"
    )
    op.execute("UPDATE manual_bonus_events SET amount = 0 WHERE amount IS NULL")
    op.alter_column(
        "manual_bonus_events",
        "amount",
        nullable=False,
        server_default="0",
    )
    op.add_column(
        "manual_bonus_events",
        sa.Column(
            "calculation_mode",
            sa.String(length=32),
            nullable=False,
            server_default="manual_amount",
        ),
    )
    op.create_table(
        "manual_bonus_adjustments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("start_month", sa.Date(), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_manual_bonus_adjustments"),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["users.id"],
            name="fk_manual_bonus_adjustments_employee",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_manual_bonus_adjustments_employee_id",
        "manual_bonus_adjustments",
        ["employee_id"],
    )
    op.create_index(
        "ix_manual_bonus_adjustments_start_month",
        "manual_bonus_adjustments",
        ["start_month"],
    )


def downgrade() -> None:
    op.drop_table("manual_bonus_adjustments")
    op.drop_column("manual_bonus_events", "calculation_mode")
    op.drop_column("manual_bonus_events", "amount")
