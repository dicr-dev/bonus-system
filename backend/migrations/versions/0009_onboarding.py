"""Add employee onboarding plans and completion facts.

Revision ID: 0009_onboarding
Revises: 0008_manual_bonus_amount
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_onboarding"
down_revision = "0008_manual_bonus_amount"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("onboarding_assignments", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("employee_id", sa.Uuid(), nullable=False), sa.Column("assigned_by_id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.ForeignKeyConstraint(["assigned_by_id"], ["users.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("employee_id"))
    op.create_index("ix_onboarding_assignments_employee_id", "onboarding_assignments", ["employee_id"])
    op.create_table("onboarding_tasks", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("assignment_id", sa.Uuid(), nullable=False), sa.Column("section", sa.String(length=255), nullable=False), sa.Column("title", sa.String(length=500), nullable=False), sa.Column("position", sa.Integer(), nullable=False), sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("comment", sa.Text(), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["assignment_id"], ["onboarding_assignments.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("assignment_id", "position", name="uq_onboarding_tasks_assignment_position"))
    op.create_index("ix_onboarding_tasks_assignment_id", "onboarding_tasks", ["assignment_id"])


def downgrade() -> None:
    op.drop_table("onboarding_tasks")
    op.drop_table("onboarding_assignments")
