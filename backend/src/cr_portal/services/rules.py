import json
from datetime import date
from decimal import Decimal
from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.models.bonus import BonusRule

DEFAULT_RULES={
 "divider":"2.5","tech_integration_rate":"0.50","sales_rate":"0.10",
 "support_hour_rate":"200","training_bonus":"2000","cr_start_fixed":"10000",
 "implementation_thresholds":[
  {"from":"0","rate":"0.10"},{"from":"100000","rate":"0.11"},
  {"from":"150000","rate":"0.12"},{"from":"175000","rate":"0.13"},
  {"from":"200000","rate":"0.15"}],
 "current_clients_tiers":[
  {"from":1,"to":99,"bonus":"1000"},{"from":100,"to":299,"bonus":"2000"},
  {"from":300,"to":499,"bonus":"3000"},{"from":500,"to":None,"bonus":"4000"}]
}
def decimal(v:Any)->Decimal: return Decimal(str(v))
def implementation_rate(total:Decimal,config:dict[str,Any])->Decimal:
    result=Decimal("0")
    for row in sorted(config.get("implementation_thresholds",DEFAULT_RULES["implementation_thresholds"]),key=lambda x:decimal(x["from"])):
        if total>=decimal(row["from"]): result=decimal(row["rate"])
    return result
def current_client_bonus(machines:int,config:dict[str,Any])->Decimal:
    for row in config.get("current_clients_tiers",DEFAULT_RULES["current_clients_tiers"]):
        if machines>=int(row["from"]) and (row.get("to") is None or machines<=int(row["to"])):
            return decimal(row["bonus"])
    return Decimal("0")
async def get_rules(session:AsyncSession,month:date)->tuple[int,dict[str,Any]]:
    r=await session.execute(select(BonusRule).where(
        BonusRule.effective_from<=month,
        or_(BonusRule.effective_to.is_(None),BonusRule.effective_to>=month)
    ).order_by(BonusRule.version.desc()).limit(1))
    row=r.scalar_one_or_none()
    if not row: return 0,DEFAULT_RULES.copy()
    try: return row.version,json.loads(row.config_json)
    except Exception: return row.version,DEFAULT_RULES.copy()
