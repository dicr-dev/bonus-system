"""release 0.2 database core"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_release_0_2_core"
down_revision: Union[str, Sequence[str], None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bitrix_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("bitrix_id", name="uq_users_bitrix_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "deals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bitrix_id", sa.Integer(), nullable=False),
        sa.Column("funnel", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("monthly_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("machines_count", sa.Integer(), nullable=False),
        sa.Column("integration_1c", sa.Boolean(), nullable=False),
        sa.Column("source_deal_id", sa.Integer(), nullable=True),
        sa.Column("implementation_responsible_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["implementation_responsible_id"],
            ["users.id"],
            name="fk_deals_implementation_responsible_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_deals"),
        sa.UniqueConstraint("bitrix_id", name="uq_deals_bitrix_id"),
    )
    op.create_index("ix_deals_bitrix_id", "deals", ["bitrix_id"])
    op.create_index("ix_deals_funnel", "deals", ["funnel"])
    op.create_index("ix_deals_status", "deals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_deals_status", table_name="deals")
    op.drop_index("ix_deals_funnel", table_name="deals")
    op.drop_index("ix_deals_bitrix_id", table_name="deals")
    op.drop_table("deals")
    op.drop_table("users")
