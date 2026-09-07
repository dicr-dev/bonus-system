"""Mark the default administrator.

Revision ID: 0006_admin_login
Revises: 0005_app_settings
"""

from alembic import op

revision = "0006_admin_login"
down_revision = "0005_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE users SET is_admin = TRUE "
        "WHERE full_name = 'Дамир Искандеров'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET is_admin = FALSE "
        "WHERE full_name = 'Дамир Искандеров'"
    )