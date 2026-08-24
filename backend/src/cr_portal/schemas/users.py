from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
class UserResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; bitrix_id: int; email: str|None; full_name: str; department_name: str|None; position: str|None; is_active: bool; is_admin: bool; created_at: datetime; updated_at: datetime
