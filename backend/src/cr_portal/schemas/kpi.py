from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlanInput(BaseModel):
    plan_value:Decimal
    comment:str|None=None

class PlanResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID;month:date;plan_value:Decimal;comment:str|None;author_id:UUID|None;created_at:datetime;updated_at:datetime

class KPIDealItem(BaseModel):
    deal_id:UUID;bitrix_id:int;title:str;amount:Decimal

class KPIPlannedDealItem(BaseModel):
    deal_id:UUID;bitrix_id:int;title:str;planned_date:date;amount:Decimal;machines_count:int

class KPISummary(BaseModel):
    month:date;plan:Decimal;fact:Decimal;plan_completion_percent:Decimal
    implementation_total:Decimal;cr_start_total:Decimal
    implementation_deals:list[KPIDealItem];cr_start_deals:list[KPIDealItem]
    planned_deals:list[KPIPlannedDealItem]

class IssueResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID;calculation_id:UUID|None;month:date;severity:str;code:str;message:str
    employee_id:UUID|None;deal_id:UUID|None;deal_bitrix_id:int|None=None;details_json:str;created_at:datetime
