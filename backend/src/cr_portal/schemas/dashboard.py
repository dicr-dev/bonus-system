from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class FunnelSummary(BaseModel):
    funnel: str
    active_deals: int
    monthly_amount: Decimal
    machines_count: int
    integration_1c_deals: int


class ResponsibleSummary(BaseModel):
    user_id: UUID
    full_name: str
    active_deals: int
    monthly_amount: Decimal
    machines_count: int


class DashboardSummary(BaseModel):
    active_deals: int
    monthly_amount: Decimal
    machines_count: int
    integration_1c_deals: int
    subscription_implementation_amount: Decimal
    subscription_cr_start_amount: Decimal
    subscription_total_amount: Decimal
    funnels: list[FunnelSummary]
    responsibles: list[ResponsibleSummary]