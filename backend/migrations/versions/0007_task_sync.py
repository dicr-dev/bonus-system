"""Cache Bitrix tasks and elapsed time for nightly synchronization.

Revision ID: 0007_task_sync
Revises: 0006_admin_login
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_task_sync"
down_revision = "0006_admin_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bitrix_tasks",
        sa.Column("bitrix_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("responsible_bitrix_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("crm_deal_ids_json", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("bitrix_id", name=op.f("pk_bitrix_tasks")),
    )
    for column in ("responsible_bitrix_id", "group_id", "synced_at"):
        op.create_index(op.f(f"ix_bitrix_tasks_{column}"), "bitrix_tasks", [column])

    op.create_table(
        "bitrix_task_elapsed_items",
        sa.Column("bitrix_id", sa.Integer(), nullable=False),
        sa.Column("task_bitrix_id", sa.Integer(), nullable=False),
        sa.Column("user_bitrix_id", sa.Integer(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["task_bitrix_id"],
            ["bitrix_tasks.bitrix_id"],
            name=op.f("fk_bitrix_task_elapsed_items_task_bitrix_id_bitrix_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("bitrix_id", name=op.f("pk_bitrix_task_elapsed_items")),
    )
    for column in ("task_bitrix_id", "user_bitrix_id", "created_time", "synced_at"):
        op.create_index(
            op.f(f"ix_bitrix_task_elapsed_items_{column}"),
            "bitrix_task_elapsed_items",
            [column],
        )


def downgrade() -> None:
    op.drop_table("bitrix_task_elapsed_items")
    op.drop_table("bitrix_tasks")
