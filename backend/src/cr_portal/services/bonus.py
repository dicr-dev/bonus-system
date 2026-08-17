from decimal import Decimal
from uuid import UUID

from cr_portal.schemas.bonus import BonusCalculationRequest, BonusResult

TRAINING_BONUS = Decimal("2000")
DIVIDER = Decimal("2.5")


def implementation_rate(total: Decimal) -> Decimal:
    if total >= Decimal("200000"):
        return Decimal("0.15")
    if total >= Decimal("175000"):
        return Decimal("0.13")
    if total >= Decimal("150000"):
        return Decimal("0.12")
    if total >= Decimal("100000"):
        return Decimal("0.11")
    return Decimal("0.10")


def calculate_bonus(request: BonusCalculationRequest) -> BonusResult:
    implementation_bonus = request.implementation_total * implementation_rate(
        request.implementation_total
    )
    tech_integration_bonus = request.tech_integration_total * Decimal("0.50")
    support_bonus = request.support_hours * Decimal("200")
    sales_bonus = request.sales_total * Decimal("0.10")
    training_bonus = Decimal(request.training_count) * TRAINING_BONUS

    subtotal = (
        implementation_bonus
        + tech_integration_bonus
        + support_bonus
        + sales_bonus
        + training_bonus
    )

    return BonusResult(
        employee_id=request.employee_id,
        implementation_bonus=implementation_bonus,
        tech_integration_bonus=tech_integration_bonus,
        support_bonus=support_bonus,
        sales_bonus=sales_bonus,
        training_bonus=training_bonus,
        total_before_divider=subtotal,
        total=subtotal / DIVIDER,
    )
