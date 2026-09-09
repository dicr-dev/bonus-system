from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from cr_portal.db.base import Base


class OnboardingAssignment(Base):
    __tablename__ = "onboarding_assignments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    assigned_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    __table_args__ = (UniqueConstraint("assignment_id", "position", name="uq_onboarding_tasks_assignment_position"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assignment_id: Mapped[UUID] = mapped_column(ForeignKey("onboarding_assignments.id", ondelete="CASCADE"), index=True)
    section: Mapped[str] = mapped_column(String(255))
    section_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OnboardingPlanSection(Base):
    __tablename__ = "onboarding_plan_sections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer)


class OnboardingPlanTask(Base):
    __tablename__ = "onboarding_plan_tasks"
    __table_args__ = (UniqueConstraint("section_id", "position", name="uq_onboarding_plan_tasks_section_position"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    section_id: Mapped[UUID] = mapped_column(ForeignKey("onboarding_plan_sections.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer)
