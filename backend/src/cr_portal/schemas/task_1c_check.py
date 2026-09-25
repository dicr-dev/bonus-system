from datetime import datetime

from pydantic import BaseModel


class Task1CCheckItem(BaseModel):
    task_bitrix_id: int
    title: str
    group_id: int | None = None
    responsible_bitrix_id: int | None = None
    deal_bitrix_id: int | None = None
    deal_title: str | None = None
    deal_funnel: str | None = None
    creator_name: str | None = None
    responsible_name: str | None = None
    created_time: datetime | None = None
    in_1c_project: bool
    has_1c_type: bool
    status: int | None = None


class Task1CCheckReport(BaseModel):
    tasks: list[Task1CCheckItem]


class Task1CCheckExportRequest(BaseModel):
    task_bitrix_ids: list[int]
