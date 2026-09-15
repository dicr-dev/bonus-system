from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from cr_portal.db.base import Base


class EmployeeMonthlyDealPlan(Base):
    __tablename__ = "employee_monthly_deal_plans"
    __table_args__ = (
        UniqueConstraint("month", "employee_id", "deal_id", name="uq_employee_monthly_deal_plan"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    month: Mapped[date] = mapped_column(Date, index=True)
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    deal_id: Mapped[UUID] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
