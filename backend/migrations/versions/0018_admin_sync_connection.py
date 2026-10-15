"""Isolate verified administrator OAuth credentials from legacy installations."""
import sqlalchemy as sa
from alembic import op

revision = "0018_admin_sync_connection"
down_revision = "0017_reporting_sync_foundation"
branch_labels = None
depends_on = None


def upgrade():
    # Never auto-promote unverified legacy credentials to the trusted connection.
    op.create_table(
        "bitrix_sync_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.String(100), nullable=False),
        sa.Column("portal_domain", sa.String(255), nullable=False),
        sa.Column("client_endpoint", sa.String(500), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admin_bitrix_user_id", sa.Integer(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("admin_bitrix_user_id > 0", name="ck_sync_admin_user_positive"),
    )
    op.create_index("ix_bitrix_sync_connections_member_id", "bitrix_sync_connections", ["member_id"], unique=True)


def downgrade():
    op.drop_index("ix_bitrix_sync_connections_member_id", table_name="bitrix_sync_connections")
    op.drop_table("bitrix_sync_connections")
