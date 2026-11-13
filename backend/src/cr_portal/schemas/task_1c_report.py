from datetime import datetime

from pydantic import BaseModel


class Task1CReportItem(BaseModel):
    task_bitrix_id: int
    title: str
    group_id: int | None = None
    responsible_bitrix_id: int | None = None
    creator_name: str | None = None
    responsible_name: str | None = None
    created_time: datetime | None = None
    deadline: datetime | None = None
    status: int | None = None
    task_1c_type: str | None = None


class Task1CDeveloperSummary(BaseModel):
    user_id: str
    full_name: str
    todo: int = 0
    in_progress: int = 0
    awaiting_review: int = 0
    completed: int = 0


class Task1CReport(BaseModel):
    tasks: list[Task1CReportItem]
    developers: list[Task1CDeveloperSummary]
