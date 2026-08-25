"""add implementation responsible to deals

Revision ID: 0003_add_implementation_responsible
Revises: 0002_add_bitrix_installation
"""
import sqlalchemy as sa
from alembic import op
revision = "0003_impl_resp"
down_revision = "0002_add_bitrix_installation"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("deals", sa.Column("implementation_responsible_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_deals_implementation_responsible_user_id_users", "deals", "users", ["implementation_responsible_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_deals_implementation_responsible_user_id", "deals", ["implementation_responsible_user_id"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_deals_implementation_responsible_user_id", table_name="deals")
    op.drop_constraint("fk_deals_implementation_responsible_user_id_users", "deals", type_="foreignkey")
    op.drop_column("deals", "implementation_responsible_user_id")
