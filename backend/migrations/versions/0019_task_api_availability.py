"""Record task card availability without deleting cached task history."""
import sqlalchemy as sa
from alembic import op

revision = "0019_task_api_availability"
down_revision = "0018_admin_sync_connection"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bitrix_tasks", sa.Column("api_available", sa.Boolean(), nullable=True))
    op.add_column("bitrix_tasks", sa.Column("api_checked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("bitrix_tasks", "api_checked_at")
    op.drop_column("bitrix_tasks", "api_available")
