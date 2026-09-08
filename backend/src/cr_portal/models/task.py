from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cr_portal.db.base import Base


class BitrixTask(Base):
    __tablename__ = "bitrix_tasks"

    bitrix_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(1000))
    responsible_bitrix_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    crm_deal_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class BitrixTaskElapsedItem(Base):
    __tablename__ = "bitrix_task_elapsed_items"

    bitrix_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_bitrix_id: Mapped[int] = mapped_column(
        ForeignKey("bitrix_tasks.bitrix_id", ondelete="CASCADE"), index=True
    )
    user_bitrix_id: Mapped[int] = mapped_column(Integer, index=True)
    seconds: Mapped[int] = mapped_column(Integer)
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
