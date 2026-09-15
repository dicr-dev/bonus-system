from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class EmployeeMonthPlanDeal(BaseModel):
    id: UUID
    bitrix_id: int
    title: str
    module: str | None = None
    machines_count: int
    integration_1c: bool
    opportunity: Decimal
    monthly_amount: Decimal


class EmployeeMonthPlan(BaseModel):
    month: date
    available_deals: list[EmployeeMonthPlanDeal]
    planned_deals: list[EmployeeMonthPlanDeal]


class AdminEmployeeMonthPlanDeal(EmployeeMonthPlanDeal):
    employee_id: UUID
    employee_name: str


class AdminEmployeeMonthPlan(BaseModel):
    month: date
    planned_deals: list[AdminEmployeeMonthPlanDeal]


class EmployeeMonthPlanAdd(BaseModel):
    deal_id: UUID
