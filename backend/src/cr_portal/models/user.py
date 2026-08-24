from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from cr_portal.db.base import Base
class User(Base):
    __tablename__="users"
    id: Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    bitrix_id: Mapped[int]=mapped_column(Integer,unique=True,index=True)
    email: Mapped[str|None]=mapped_column(String(255),nullable=True)
    full_name: Mapped[str]=mapped_column(String(255))
    department_name: Mapped[str|None]=mapped_column(String(255),nullable=True)
    position: Mapped[str|None]=mapped_column(String(255),nullable=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    is_admin: Mapped[bool]=mapped_column(Boolean,default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
    deals: Mapped[list["Deal"]]=relationship(back_populates="responsible_user")
