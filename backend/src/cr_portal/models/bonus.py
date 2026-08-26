from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from cr_portal.db.base import Base

class BonusRule(Base):
    __tablename__="bonus_rules"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    version: Mapped[int]=mapped_column(Integer,unique=True)
    effective_from: Mapped[date]=mapped_column(Date,index=True)
    effective_to: Mapped[date|None]=mapped_column(Date,nullable=True)
    config_json: Mapped[str]=mapped_column(Text)
    comment: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class BonusCalculation(Base):
    __tablename__="bonus_calculations"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    employee_id: Mapped[UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    period_from: Mapped[date]=mapped_column(Date)
    period_to: Mapped[date]=mapped_column(Date)
    implementation_total: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    tech_integration_total: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    support_hours: Mapped[Decimal]=mapped_column(Numeric(10,2),default=0)
    sales_total: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    training_count: Mapped[int]=mapped_column(Integer,default=0)
    total_bonus: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    details_json: Mapped[str]=mapped_column(Text,default="{}")
    month: Mapped[date|None]=mapped_column(Date,nullable=True,index=True)
    version: Mapped[int]=mapped_column(Integer,default=1)
    status: Mapped[str]=mapped_column(String(32),default="completed")
    rules_version: Mapped[int|None]=mapped_column(Integer,nullable=True)
    rules_snapshot_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    subtotal_dividable: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    cr_start_fixed_total: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    issues_count: Mapped[int]=mapped_column(Integer,default=0)
    initiated_by_id: Mapped[UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    items: Mapped[list["BonusCalculationItem"]]=relationship(back_populates="calculation",cascade="all, delete-orphan")

class BonusCalculationItem(Base):
    __tablename__="bonus_calculation_items"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    calculation_id: Mapped[UUID]=mapped_column(ForeignKey("bonus_calculations.id",ondelete="CASCADE"),index=True)
    employee_id: Mapped[UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    deal_id: Mapped[UUID|None]=mapped_column(ForeignKey("deals.id",ondelete="SET NULL"),nullable=True,index=True)
    bonus_type: Mapped[str]=mapped_column(String(64),index=True)
    source_type: Mapped[str]=mapped_column(String(32),default="deal")
    source_external_id: Mapped[str|None]=mapped_column(String(128),nullable=True)
    base_amount: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    rate: Mapped[Decimal]=mapped_column(Numeric(14,6),default=0)
    quantity: Mapped[Decimal]=mapped_column(Numeric(14,2),default=1)
    amount_before_divider: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    divider_applied: Mapped[bool]=mapped_column(Boolean,default=True)
    amount_final: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    description: Mapped[str]=mapped_column(Text)
    details_json: Mapped[str]=mapped_column(Text,default="{}")
    calculation: Mapped["BonusCalculation"]=relationship(back_populates="items")

class ManualBonusEvent(Base):
    __tablename__="manual_bonus_events"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    event_date: Mapped[date]=mapped_column(Date,index=True)
    employee_id: Mapped[UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    deal_id: Mapped[UUID|None]=mapped_column(ForeignKey("deals.id",ondelete="SET NULL"),nullable=True)
    event_type: Mapped[str]=mapped_column(String(32),index=True)
    quantity: Mapped[Decimal]=mapped_column(Numeric(14,2),default=1)
    comment: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
