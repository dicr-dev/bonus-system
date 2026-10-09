from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from cr_portal.db.base import Base


class DealStageHistory(Base):
    __tablename__ = "deal_stage_history"
    __table_args__ = (UniqueConstraint("bitrix_event_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    bitrix_event_id: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    stage_id: Mapped[str] = mapped_column(String(100), index=True)
    stage_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    semantic: Mapped[str | None] = mapped_column(String(16), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportField(Base):
    __tablename__ = "report_fields"
    __table_args__ = (UniqueConstraint("entity_type", "code"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    code: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    field_type: Mapped[str] = mapped_column(String(100), default="string")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SavedReport(Base):
    __tablename__ = "saved_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), index=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private", index=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
