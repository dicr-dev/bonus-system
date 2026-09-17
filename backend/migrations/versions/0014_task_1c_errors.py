"""Store task creator and 1C task-type validation state.

Revision ID: 0014_task_1c_errors
Revises: 0013_deal_module_name
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_task_1c_errors"
down_revision = "0013_deal_module_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bitrix_tasks", sa.Column("creator_bitrix_id", sa.Integer(), nullable=True))
    op.add_column("bitrix_tasks", sa.Column("status", sa.Integer(), nullable=True))
    op.add_column("bitrix_tasks", sa.Column("start_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "bitrix_tasks",
        sa.Column("task_1c_type_missing", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_bitrix_tasks_creator_bitrix_id", "bitrix_tasks", ["creator_bitrix_id"])
    op.create_index("ix_bitrix_tasks_start_time", "bitrix_tasks", ["start_time"])
    op.create_index("ix_bitrix_tasks_task_1c_type_missing", "bitrix_tasks", ["task_1c_type_missing"])


def downgrade() -> None:
    op.drop_index("ix_bitrix_tasks_task_1c_type_missing", table_name="bitrix_tasks")
    op.drop_index("ix_bitrix_tasks_start_time", table_name="bitrix_tasks")
    op.drop_index("ix_bitrix_tasks_creator_bitrix_id", table_name="bitrix_tasks")
    op.drop_column("bitrix_tasks", "task_1c_type_missing")
    op.drop_column("bitrix_tasks", "start_time")
    op.drop_column("bitrix_tasks", "status")
    op.drop_column("bitrix_tasks", "creator_bitrix_id")
