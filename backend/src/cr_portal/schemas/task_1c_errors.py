from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Task1CError(BaseModel):
    task_bitrix_id: int
    title: str
    group_id: int | None = None
    responsible_bitrix_id: int | None = None
    creator_id: UUID
    creator_name: str
    start_time: datetime
    status: int | None = None


class Task1CErrorReport(BaseModel):
    tasks: list[Task1CError]
