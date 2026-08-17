from decimal import Decimal

from cr_portal.schemas.bonus import BonusCalculationRequest
from cr_portal.services.bonus import calculate_bonus


def test_bonus_uses_15_percent_at_200k() -> None:
    result = calculate_bonus(
        BonusCalculationRequest(implementation_total=Decimal("200000"))
    )
    assert result.implementation_bonus == Decimal("30000")
    assert result.total == Decimal("12000")
