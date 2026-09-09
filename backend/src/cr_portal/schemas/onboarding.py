from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OnboardingTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    section: str
    section_details: str | None
    title: str
    details: str | None
    position: int
    is_completed: bool
    comment: str | None
    completed_at: datetime | None


class OnboardingAssignmentResponse(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str
    assigned_by_name: str
    created_at: datetime
    tasks: list[OnboardingTaskResponse]


class OnboardingTaskUpdate(BaseModel):
    is_completed: bool
    comment: str | None = Field(default=None, max_length=5000)


class OnboardingPlanTaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    details: str | None = Field(default=None, max_length=10000)


class OnboardingPlanSectionInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    details: str | None = Field(default=None, max_length=10000)
    tasks: list[OnboardingPlanTaskInput] = Field(min_length=1)


class OnboardingPlanInput(BaseModel):
    sections: list[OnboardingPlanSectionInput] = Field(min_length=1)


class OnboardingPlanTaskResponse(OnboardingPlanTaskInput):
    id: UUID
    position: int


class OnboardingPlanSectionResponse(OnboardingPlanSectionInput):
    id: UUID
    position: int
    tasks: list[OnboardingPlanTaskResponse]
