from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
class BonusInput(BaseModel):
    employee_id: UUID; period_from: date; period_to: date; implementation_total: Decimal=Decimal("0"); tech_integration_total: Decimal=Decimal("0"); support_hours: Decimal=Decimal("0"); sales_total: Decimal=Decimal("0"); training_count: int=0
class BonusResult(BaseModel):
    employee_id: UUID; implementation_bonus: Decimal; tech_integration_bonus: Decimal; support_bonus: Decimal; sales_bonus: Decimal; training_bonus: Decimal; subtotal: Decimal; total: Decimal
