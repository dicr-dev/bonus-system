from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from cr_portal.models.deal import DealFunnel, DealStatus


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bitrix_id: int
    funnel: DealFunnel
    status: DealStatus
    title: str
    total_amount: Decimal
    monthly_amount: Decimal
    machines_count: int
    integration_1c: bool
    implementation_responsible_id: UUID | None
    completed_at: date | None
    created_at: datetime
    updated_at: datetime
