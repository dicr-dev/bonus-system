"""add Bitrix installation table

Revision ID: 0002_add_bitrix_installation
Revises: 0001_baseline
"""

import sqlalchemy as sa
from alembic import op


revision = "0002_add_bitrix_installation"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bitrix_installations",
        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "member_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "portal_domain",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "client_endpoint",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            "access_token",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "refresh_token",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_bitrix_installations",
        ),
        sa.UniqueConstraint(
            "member_id",
            name="uq_bitrix_installations_member_id",
        ),
    )

    op.create_index(
        "ix_bitrix_installations_member_id",
        "bitrix_installations",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bitrix_installations_member_id",
        table_name="bitrix_installations",
    )

    op.drop_table(
        "bitrix_installations",
    )