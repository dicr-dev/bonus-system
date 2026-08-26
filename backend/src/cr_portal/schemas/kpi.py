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

class KPIEmployeeContribution(BaseModel):
    employee_id:UUID|None
    employee_name:str
    implementation:int
    cr_start:int
    fact:int

class KPIDealItem(BaseModel):
    deal_id:UUID;bitrix_id:int;title:str;funnel:str;employee_name:str|None;monthly_amount:Decimal;machines_count:int

class KPISummary(BaseModel):
    month:date;plan:Decimal;fact:Decimal;implementation_fact:int;cr_start_fact:int;remaining:Decimal
    completion_percent:Decimal;potential:int;forecast:Decimal;employees:list[KPIEmployeeContribution]
    result_deals:list[KPIDealItem];potential_deals:list[KPIDealItem]

class IssueResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID;calculation_id:UUID|None;month:date;severity:str;code:str;message:str
    employee_id:UUID|None;deal_id:UUID|None;details_json:str;created_at:datetime
