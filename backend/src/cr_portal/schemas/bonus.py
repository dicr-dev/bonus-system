from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuleConfig(BaseModel):
    divider: Decimal
    tech_integration_rate: Decimal
    sales_rate: Decimal
    support_hour_rate: Decimal
    training_bonus: Decimal
    cr_start_fixed: Decimal
    implementation_thresholds: list[dict]
    current_clients_tiers: list[dict]


class RuleCreate(BaseModel):
    effective_from: date
    config: RuleConfig
    comment: str | None = None


class RuleVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    effective_from: date
    effective_to: date | None
    config_json: str
    comment: str | None
    created_at: datetime


class CalculationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    employee_name: str | None = None
    period_from: date
    period_to: date
    month: date | None
    version: int
    status: str
    rules_version: int | None
    implementation_total: Decimal
    tech_integration_total: Decimal
    support_hours: Decimal
    sales_total: Decimal
    training_count: int
    subtotal_dividable: Decimal
    cr_start_fixed_total: Decimal
    current_client_total: Decimal = Decimal("0")
    kpi_total: Decimal = Decimal("0")
    kpi_divided_total: Decimal = Decimal("0")
    total_bonus: Decimal
    issues_count: int
    created_at: datetime


class CalculationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    calculation_id: UUID
    employee_id: UUID
    deal_id: UUID | None
    deal_title: str | None = None
    deal_bitrix_id: int | None = None
    bonus_type: str
    source_type: str
    source_external_id: str | None
    base_amount: Decimal
    rate: Decimal
    quantity: Decimal
    amount_before_divider: Decimal
    divider_applied: bool
    amount_final: Decimal
    description: str
    details_json: str


class CalculationDetail(CalculationResponse):
    employee_name: str
    items: list[CalculationItemResponse]


class ManualEventCreate(BaseModel):
    event_date: date
    employee_id: UUID
    deal_id: UUID | None = None
    event_type: str = Field(pattern="^(support_hours|training)$")
    quantity: Decimal = Decimal("1")
    comment: str | None = None


class ManualEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_date: date
    employee_id: UUID
    deal_id: UUID | None
    event_type: str
    quantity: Decimal
    comment: str | None


# Backward-compatible aggregate calculator schema.
# Kept for existing tests/legacy API; production calculations use /calculations.
class BonusInput(BaseModel):
    employee_id: UUID
    period_from: date
    period_to: date
    implementation_total: Decimal = Decimal("0")
    tech_integration_total: Decimal = Decimal("0")
    support_hours: Decimal = Decimal("0")
    sales_total: Decimal = Decimal("0")
    training_count: int = 0
    cr_start_fixed_total: Decimal = Decimal("0")


class BonusResult(BaseModel):
    employee_id: UUID
    implementation_bonus: Decimal
    tech_integration_bonus: Decimal
    support_bonus: Decimal
    sales_bonus: Decimal
    training_bonus: Decimal
    cr_start_fixed_bonus: Decimal
    subtotal: Decimal
    total: Decimal
