"""Portal-owned training records; Bitrix synchronization never overwrites these tables."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cr_portal.db.base import Base


class TrainingRubric(Base):
    __tablename__ = "training_rubrics"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    criteria: Mapped[list] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainingSession(Base):
    __tablename__ = "training_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"), index=True)
    trainer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    trainer_name: Mapped[str] = mapped_column(String(255))
    training_date: Mapped[date] = mapped_column(Date, index=True)
    module: Mapped[str] = mapped_column(String(255))
    training_number: Mapped[int] = mapped_column(Integer)
    speaker_label: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    # Deferred so listing sessions doesn't read attachments or entire transcripts.
    file_content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    transcript: Mapped[str] = mapped_column(Text, deferred=True)
    extraction_info: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainingReview(Base):
    __tablename__ = "training_reviews"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    training_id: Mapped[UUID] = mapped_column(
        ForeignKey("training_sessions.id", ondelete="RESTRICT"), index=True,
    )
    rubric_id: Mapped[UUID] = mapped_column(ForeignKey("training_rubrics.id", ondelete="RESTRICT"))
    assessment: Mapped[dict] = mapped_column(JSONB)
    total: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TrainingVideo(Base):
    """One externally transcribed recording; source video is never retained."""
    __tablename__ = "training_videos"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mymeet_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="found")
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    speakers: Mapped[list] = mapped_column(JSONB, default=list)
    detected_trainer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
