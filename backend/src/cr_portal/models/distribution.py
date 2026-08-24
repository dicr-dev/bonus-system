from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from cr_portal.db.base import Base
class DistributionDecision(Base):
    __tablename__="distribution_decisions"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    deal_id: Mapped[UUID]=mapped_column(ForeignKey("deals.id",ondelete="CASCADE"),index=True)
    proposed_user_id: Mapped[UUID]=mapped_column(ForeignKey("users.id"),index=True)
    confirmed_user_id: Mapped[UUID|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    status: Mapped[str]=mapped_column(String(32),default="proposed")
    reason: Mapped[str]=mapped_column(Text,default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    resolved_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
