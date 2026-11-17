"""External training-video transcription state."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021_training_videos"
down_revision = "0020_training_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "training_videos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("deal_id", sa.Uuid(), sa.ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64)),
        sa.Column("mymeet_id", sa.String(100), unique=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("transcript", sa.Text()),
        sa.Column("speakers", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("detected_trainer_name", sa.String(255)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_training_videos_deal_id", "training_videos", ["deal_id"])
    op.create_index("ix_training_videos_source_hash", "training_videos", ["source_hash"])
    op.create_index("ix_training_videos_status", "training_videos", ["status"])


def downgrade():
    op.drop_table("training_videos")
