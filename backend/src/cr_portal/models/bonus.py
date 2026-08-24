from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from cr_portal.db.base import Base
class BonusCalculation(Base):
    __tablename__="bonus_calculations"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    employee_id: Mapped[UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    period_from: Mapped[date]=mapped_column(Date); period_to: Mapped[date]=mapped_column(Date)
    implementation_total: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    tech_integration_total: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    support_hours: Mapped[Decimal]=mapped_column(Numeric(10,2),default=0)
    sales_total: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    training_count: Mapped[int]=mapped_column(default=0)
    total_bonus: Mapped[Decimal]=mapped_column(Numeric(14,2)); details_json: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
