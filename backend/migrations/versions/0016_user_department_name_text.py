"""Allow all Bitrix departments to be stored for a user.

Revision ID: 0016_user_department_name_text
Revises: 0015_deal_company_display
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_user_department_name_text"
down_revision = "0015_deal_company_display"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "department_name",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "department_name",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
