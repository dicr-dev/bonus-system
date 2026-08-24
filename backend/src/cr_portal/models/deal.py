from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from cr_portal.db.base import Base
class FunnelCode(StrEnum):
    TECH_INTEGRATION="tech_integration"; IMPLEMENTATION="implementation"; CR_START="cr_start"; SUPPORT="support"
class DealStatus(StrEnum):
    IN_PROGRESS="in_progress"; SUCCESS="success"; FAILED="failed"
class Deal(Base):
    __tablename__="deals"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    bitrix_id: Mapped[int]=mapped_column(Integer,unique=True,index=True)
    category_id: Mapped[int]=mapped_column(Integer,index=True)
    funnel: Mapped[str]=mapped_column(String(32),index=True)
    stage_id: Mapped[str]=mapped_column(String(100),index=True)
    status: Mapped[str]=mapped_column(String(32),index=True)
    title: Mapped[str]=mapped_column(String(500))
    opportunity: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    monthly_amount: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    machines_count: Mapped[int]=mapped_column(Integer,default=0)
    integration_1c: Mapped[bool]=mapped_column(Boolean,default=False)
    bitrix_assigned_by_id: Mapped[int|None]=mapped_column(Integer,nullable=True,index=True)
    responsible_user_id: Mapped[UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    raw_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_time: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    closed_time: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    synced_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    responsible_user: Mapped["User|None"]=relationship(back_populates="deals")
