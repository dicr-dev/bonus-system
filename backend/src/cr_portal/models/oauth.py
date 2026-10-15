from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cr_portal.db.base import Base


class BitrixInstallation(Base):
    __tablename__ = "bitrix_installations"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    member_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )

    portal_domain: Mapped[str] = mapped_column(
        String(255),
    )

    client_endpoint: Mapped[str] = mapped_column(
        String(500),
    )

    access_token: Mapped[str] = mapped_column(
        Text,
    )

    refresh_token: Mapped[str] = mapped_column(
        Text,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class BitrixSyncConnection(Base):
    """Administrator-only credentials. Legacy installation writers cannot touch this table."""
    __tablename__ = "bitrix_sync_connections"
    __table_args__ = (CheckConstraint("admin_bitrix_user_id > 0", name="ck_sync_admin_user_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    member_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    portal_domain: Mapped[str] = mapped_column(String(255))
    client_endpoint: Mapped[str] = mapped_column(String(500))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    admin_bitrix_user_id: Mapped[int] = mapped_column(Integer)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
