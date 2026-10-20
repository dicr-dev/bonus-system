from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Criterion(StrictInput):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    title: str = Field(min_length=3, max_length=200)
    weight: int = Field(ge=1, le=100, strict=True)


class RubricInput(StrictInput):
    title: str = Field(min_length=3, max_length=200)
    criteria: list[Criterion] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def valid_weights(self):
        if sum(c.weight for c in self.criteria) != 100:
            raise ValueError("Сумма весов должна составлять 100%")
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Коды критериев должны быть уникальными")
        return self


class TrainingInput(StrictInput):
    deal_id: UUID
    trainer_id: UUID
    training_date: date
    module: str = Field(min_length=1, max_length=255)
    training_number: int = Field(ge=1, le=3)
    speaker_label: str = Field(min_length=1, max_length=200)


class Evidence(StrictInput):
    quote: str = Field(min_length=8, max_length=2000)
    timecode: str = Field(default="", max_length=30)


class CriterionAssessment(StrictInput):
    id: str = Field(min_length=1, max_length=40)
    score: Decimal | None = Field(ge=0, le=10)
    explanation: str = Field(min_length=10, max_length=5000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=10)


class ReviewInput(StrictInput):
    # Echoed by ChatGPT; prevents accidentally importing a result for another training/version.
    training_id: UUID
    rubric_id: UUID
    criteria: list[CriterionAssessment] = Field(min_length=1, max_length=20)
    strengths: str = Field(default="", max_length=10000)
    recommendations: str = Field(default="", max_length=10000)
    limitations: str = Field(default="", max_length=5000)

    @field_validator("criteria")
    @classmethod
    def unique_criteria(cls, value):
        if len({c.id for c in value}) != len(value):
            raise ValueError("Критерии не должны повторяться")
        return value
