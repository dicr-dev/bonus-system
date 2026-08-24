from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict
class DealResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; bitrix_id: int; category_id: int; funnel: str; stage_id: str; status: str; title: str; opportunity: Decimal; monthly_amount: Decimal; machines_count: int; integration_1c: bool; bitrix_assigned_by_id: int|None; responsible_user_id: UUID|None; created_time: datetime|None; closed_time: datetime|None
