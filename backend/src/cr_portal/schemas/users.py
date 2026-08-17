from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bitrix_id: int | None
    email: str | None
    full_name: str
    is_active: bool
    created_at: datetime
