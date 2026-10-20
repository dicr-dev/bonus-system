"""Administrator-only training transcripts and immutable assessment versions."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0020_training_reviews"
down_revision = "0019_task_api_availability"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "training_rubrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "training_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("deal_id", sa.Uuid(), sa.ForeignKey("deals.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trainer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trainer_name", sa.String(255), nullable=False),
        sa.Column("training_date", sa.Date(), nullable=False),
        sa.Column("module", sa.String(255), nullable=False),
        sa.Column("training_number", sa.Integer(), nullable=False),
        sa.Column("speaker_label", sa.String(200), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("file_content", sa.LargeBinary(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("extraction_info", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("deal_id", "trainer_id", "training_date"):
        op.create_index(f"ix_training_sessions_{column}", "training_sessions", [column])
    op.create_table(
        "training_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("training_id", sa.Uuid(), sa.ForeignKey("training_sessions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rubric_id", sa.Uuid(), sa.ForeignKey("training_rubrics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assessment", postgresql.JSONB(), nullable=False),
        sa.Column("total", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_reviews_training_id", "training_reviews", ["training_id"])


def downgrade():
    op.drop_table("training_reviews")
    op.drop_table("training_sessions")
    op.drop_table("training_rubrics")
