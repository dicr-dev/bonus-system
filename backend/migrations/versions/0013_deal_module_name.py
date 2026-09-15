"""Store display name of deal module.

Revision ID: 0013_deal_module_name
Revises: 0012_deal_plan_display_fields
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_deal_module_name"
down_revision = "0012_deal_plan_display_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("module_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "module_name")
