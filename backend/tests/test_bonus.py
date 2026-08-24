from datetime import date
from decimal import Decimal
from uuid import uuid4
from cr_portal.schemas.bonus import BonusInput
from cr_portal.services.bonus import calculate_bonus
def test_bonus():
 d=BonusInput(employee_id=uuid4(),period_from=date(2026,8,1),period_to=date(2026,8,31),implementation_total=Decimal('200000')); r=calculate_bonus(d); assert r.implementation_bonus==Decimal('30000'); assert r.total==Decimal('12000')