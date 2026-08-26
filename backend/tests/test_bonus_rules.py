from decimal import Decimal
from cr_portal.services.rules import DEFAULT_RULES,current_client_bonus,implementation_rate
def test_thresholds():
    assert implementation_rate(Decimal("99999.99"),DEFAULT_RULES)==Decimal("0.10")
    assert implementation_rate(Decimal("100000"),DEFAULT_RULES)==Decimal("0.11")
    assert implementation_rate(Decimal("150000"),DEFAULT_RULES)==Decimal("0.12")
    assert implementation_rate(Decimal("175000"),DEFAULT_RULES)==Decimal("0.13")
    assert implementation_rate(Decimal("200000"),DEFAULT_RULES)==Decimal("0.15")
def test_machine_boundaries():
    assert current_client_bonus(99,DEFAULT_RULES)==Decimal("1000")
    assert current_client_bonus(100,DEFAULT_RULES)==Decimal("2000")
    assert current_client_bonus(299,DEFAULT_RULES)==Decimal("2000")
    assert current_client_bonus(300,DEFAULT_RULES)==Decimal("3000")
    assert current_client_bonus(499,DEFAULT_RULES)==Decimal("3000")
    assert current_client_bonus(500,DEFAULT_RULES)==Decimal("4000")
