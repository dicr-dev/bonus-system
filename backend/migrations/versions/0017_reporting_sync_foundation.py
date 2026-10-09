"""Add reporting builder and deal stage history storage.

Revision ID: 0017_reporting_sync_foundation
Revises: 0016_user_department_name_text
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_reporting_sync_foundation"
down_revision = "0016_user_department_name_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deal_stage_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("bitrix_event_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("stage_id", sa.String(length=100), nullable=False),
        sa.Column("stage_title", sa.String(length=255), nullable=True),
        sa.Column("semantic", sa.String(length=16), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bitrix_event_id"),
    )
    op.create_index("ix_deal_stage_history_deal_id", "deal_stage_history", ["deal_id"])
    op.create_index("ix_deal_stage_history_category_id", "deal_stage_history", ["category_id"])
    op.create_index("ix_deal_stage_history_stage_id", "deal_stage_history", ["stage_id"])
    op.create_index("ix_deal_stage_history_occurred_at", "deal_stage_history", ["occurred_at"])
    op.create_table(
        "report_fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("field_type", sa.String(length=100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "code"),
    )
    op.create_index("ix_report_fields_entity_type", "report_fields", ["entity_type"])
    op.create_index("ix_report_fields_is_enabled", "report_fields", ["is_enabled"])
    op.create_table(
        "saved_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_reports_source", "saved_reports", ["source"])
    op.create_index("ix_saved_reports_visibility", "saved_reports", ["visibility"])
    op.create_index("ix_saved_reports_author_id", "saved_reports", ["author_id"])


def downgrade() -> None:
    op.drop_table("saved_reports")
    op.drop_table("report_fields")
    op.drop_table("deal_stage_history")
