from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from cr_portal.db.base import Base

class MonthlyPlan(Base):
    __tablename__="monthly_plans"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    month: Mapped[date]=mapped_column(Date,unique=True,index=True)
    plan_value: Mapped[Decimal]=mapped_column(Numeric(14,2))
    comment: Mapped[str|None]=mapped_column(Text,nullable=True)
    author_id: Mapped[UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())

class KPIEvent(Base):
    __tablename__="kpi_events"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    event_key: Mapped[str]=mapped_column(String(128),unique=True)
    month: Mapped[date]=mapped_column(Date,index=True)
    event_date: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    event_type: Mapped[str]=mapped_column(String(64),index=True)
    employee_id: Mapped[UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    deal_id: Mapped[UUID]=mapped_column(ForeignKey("deals.id",ondelete="CASCADE"))
    value: Mapped[Decimal]=mapped_column(Numeric(14,2),default=1)
    details_json: Mapped[str]=mapped_column(Text,default="{}")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class CalculationIssue(Base):
    __tablename__="calculation_issues"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    calculation_id: Mapped[UUID|None]=mapped_column(ForeignKey("bonus_calculations.id",ondelete="CASCADE"),nullable=True)
    month: Mapped[date]=mapped_column(Date,index=True)
    severity: Mapped[str]=mapped_column(String(16),index=True)
    code: Mapped[str]=mapped_column(String(64),index=True)
    message: Mapped[str]=mapped_column(Text)
    employee_id: Mapped[UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    deal_id: Mapped[UUID|None]=mapped_column(ForeignKey("deals.id",ondelete="SET NULL"),nullable=True)
    details_json: Mapped[str]=mapped_column(Text,default="{}")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
