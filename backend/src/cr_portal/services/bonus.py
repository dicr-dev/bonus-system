from decimal import Decimal
from cr_portal.schemas.bonus import BonusInput, BonusResult
DIVIDER=Decimal("2.5"); TRAINING_BONUS=Decimal("2000")
def implementation_rate(total: Decimal)->Decimal:
    if total>=Decimal("200000"): return Decimal("0.15")
    if total>=Decimal("175000"): return Decimal("0.13")
    if total>=Decimal("150000"): return Decimal("0.12")
    if total>=Decimal("100000"): return Decimal("0.11")
    return Decimal("0.10")
def calculate_bonus(d: BonusInput)->BonusResult:
    a=d.implementation_total*implementation_rate(d.implementation_total); b=d.tech_integration_total*Decimal("0.50"); c=d.support_hours*Decimal("200"); e=d.sales_total*Decimal("0.10"); f=Decimal(d.training_count)*TRAINING_BONUS; s=a+b+c+e+f
    return BonusResult(employee_id=d.employee_id,implementation_bonus=a,tech_integration_bonus=b,support_bonus=c,sales_bonus=e,training_bonus=f,subtotal=s,total=s/DIVIDER)
