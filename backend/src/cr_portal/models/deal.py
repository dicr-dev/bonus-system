from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cr_portal.db.base import Base


class DealFunnel(StrEnum):
    TECH_INTEGRATION = "tech_integration"
    IMPLEMENTATION = "implementation"
    SUPPORT = "support"
    CR_START = "cr_start"


class DealStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    bitrix_id: Mapped[int] = mapped_column(unique=True, index=True)
    funnel: Mapped[DealFunnel] = mapped_column(String(32), index=True)
    status: Mapped[DealStatus] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(500))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    machines_count: Mapped[int] = mapped_column(default=0)
    integration_1c: Mapped[bool] = mapped_column(default=False)
    source_deal_id: Mapped[int | None] = mapped_column()
    implementation_responsible_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    responsible_user: Mapped["User | None"] = relationship(back_populates="deals")
