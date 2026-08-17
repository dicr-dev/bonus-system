from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class BonusResult(BaseModel):
    employee_id: UUID | None
    implementation_bonus: Decimal
    tech_integration_bonus: Decimal
    support_bonus: Decimal
    sales_bonus: Decimal
    training_bonus: Decimal
    total_before_divider: Decimal
    total: Decimal


class BonusCalculationRequest(BaseModel):
    employee_id: UUID | None = None
    implementation_total: Decimal = Decimal("0")
    tech_integration_total: Decimal = Decimal("0")
    support_hours: Decimal = Decimal("0")
    sales_total: Decimal = Decimal("0")
    training_count: int = 0
