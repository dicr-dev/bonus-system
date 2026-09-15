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
    funnel: str
    deal_current_status: str | None = None
    stage_title: str | None = None
    timely_request_percent: Decimal | None = None
    planned_subscription_date: date | None = None
    implementation_planned_billing_start: date | None = None
    implementation_planned_subscription: date | None = None
    billing_start_date: date | None = None
    salesperson_name: str | None = None
    implementation_responsible_name: str | None = None
    integration_amount: Decimal | None = None
    first_training_date: date | None = None
    second_training_date: date | None = None
    reports_training_date: date | None = None
    cr_company_id: str | None = None


class AdminEmployeeMonthPlan(BaseModel):
    month: date
    planned_deals: list[AdminEmployeeMonthPlanDeal]


class EmployeeMonthPlanAdd(BaseModel):
    deal_id: UUID
