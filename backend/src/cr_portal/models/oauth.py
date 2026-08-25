from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
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