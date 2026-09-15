from datetime import date
from uuid import UUID

from pydantic import BaseModel


class TimeReportTask(BaseModel):
    task_bitrix_id: int
    title: str
    seconds: int
    group_id: int | None = None
    responsible_bitrix_id: int | None = None


class TimeReportDay(BaseModel):
    date: date
    seconds: int
    tasks: list[TimeReportTask]


class TimeReportEmployee(BaseModel):
    employee_id: UUID
    full_name: str
    department_name: str | None = None
    total_seconds: int
    days: list[TimeReportDay]


class TimeReport(BaseModel):
    date_from: date
    date_to: date
    days: list[date]
    employees: list[TimeReportEmployee]
