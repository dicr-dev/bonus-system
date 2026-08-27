"""Editable application business settings.

Revision ID: 0005_app_settings
Revises: 0004_kpi_bonus
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_app_settings"
down_revision = "0004_kpi_bonus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
