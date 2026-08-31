from datetime import date
from decimal import Decimal
from uuid import uuid4
from cr_portal.schemas.bonus import BonusInput
from cr_portal.services.bonus import bonus_month_number, calculate_bonus


def test_bonus():
 d=BonusInput(employee_id=uuid4(),period_from=date(2026,8,1),period_to=date(2026,8,31),implementation_total=Decimal('200000')); r=calculate_bonus(d); assert r.implementation_bonus==Decimal('30000'); assert r.total==Decimal('12000')


def test_bonus_month_number():
 assert bonus_month_number(date(2026, 8, 1), date(2026, 8, 1)) == 1
 assert bonus_month_number(date(2026, 9, 1), date(2026, 8, 1)) == 2
 assert bonus_month_number(date(2026, 10, 1), date(2026, 8, 1)) == 3
 assert bonus_month_number(date(2026, 11, 1), date(2026, 8, 1)) == 4