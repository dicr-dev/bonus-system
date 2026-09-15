import json
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.models.task import BitrixTask, BitrixTaskElapsedItem
from cr_portal.models.user import User
from cr_portal.services.employee_scope import KPI_DEPARTMENT_NAMES, employee_is_in_department

MOSCOW = ZoneInfo("Europe/Moscow")


def _dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=index) for index in range((end - start).days + 1)]


def _task_deal_ids(task: BitrixTask | None) -> list[int]:
    if task is None:
        return []
    try:
        values = json.loads(task.crm_deal_ids_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [int(value) for value in values if str(value).isdigit()]


async def time_spent_report(
    session: AsyncSession,
    *,
    date_from: date,
    date_to: date,
    departments: list[str],
    employee_ids: list[UUID],
    funnels: list[str],
    current_user: User,
    current_user_only: bool = False,
) -> dict:
    if date_to < date_from:
        raise ValueError("Дата окончания не может быть раньше даты начала")

    users = list((await session.execute(select(User).where(User.is_active.is_(True)))).scalars().all())
    if current_user_only:
        allowed_users = [current_user]
    elif current_user.is_admin:
        allowed_users = [
            user for user in users
            if any(employee_is_in_department(user, department) for department in KPI_DEPARTMENT_NAMES)
        ]
        if departments:
            allowed_users = [
                user for user in allowed_users
                if any(employee_is_in_department(user, department) for department in departments)
            ]
        if employee_ids:
            requested = set(employee_ids)
            allowed_users = [user for user in allowed_users if user.id in requested]
    else:
        allowed_users = [current_user]

    users_by_bitrix_id = {user.bitrix_id: user for user in allowed_users}
    if not users_by_bitrix_id:
        return {"date_from": date_from, "date_to": date_to, "days": _dates(date_from, date_to), "employees": []}

    start = datetime.combine(date_from, time.min, MOSCOW).astimezone(UTC)
    end = datetime.combine(date_to + timedelta(days=1), time.min, MOSCOW).astimezone(UTC)
    rows = (await session.execute(
        select(BitrixTaskElapsedItem, BitrixTask)
        .outerjoin(BitrixTask, BitrixTask.bitrix_id == BitrixTaskElapsedItem.task_bitrix_id)
        .where(
            BitrixTaskElapsedItem.user_bitrix_id.in_(users_by_bitrix_id),
            BitrixTaskElapsedItem.created_time >= start,
            BitrixTaskElapsedItem.created_time < end,
            BitrixTaskElapsedItem.seconds > 0,
        )
    )).all()

    deal_ids = {deal_id for _, task in rows for deal_id in _task_deal_ids(task)}
    deals_by_id = {}
    if deal_ids:
        deals_by_id = {
            deal.bitrix_id: deal
            for deal in (await session.execute(select(Deal).where(Deal.bitrix_id.in_(deal_ids)))).scalars().all()
        }

    grouped: dict[UUID, dict[date, dict[int, dict]]] = defaultdict(lambda: defaultdict(dict))
    for elapsed, task in rows:
        task_funnels = {deals_by_id[deal_id].funnel for deal_id in _task_deal_ids(task) if deal_id in deals_by_id}
        if funnels and not task_funnels.intersection(funnels):
            continue
        user = users_by_bitrix_id[elapsed.user_bitrix_id]
        day = elapsed.created_time.astimezone(MOSCOW).date()
        entry = grouped[user.id][day].setdefault(elapsed.task_bitrix_id, {
            "task_bitrix_id": elapsed.task_bitrix_id,
            "title": task.title if task else f"Задача #{elapsed.task_bitrix_id}",
            "seconds": 0,
            "group_id": task.group_id if task else None,
            "responsible_bitrix_id": task.responsible_bitrix_id if task else None,
        })
        entry["seconds"] += elapsed.seconds

    employees = []
    for user in sorted(allowed_users, key=lambda item: item.full_name.casefold()):
        day_rows = []
        for day, tasks in sorted(grouped[user.id].items()):
            task_rows = sorted(tasks.values(), key=lambda item: item["title"].casefold())
            day_rows.append({"date": day, "seconds": sum(item["seconds"] for item in task_rows), "tasks": task_rows})
        employees.append({
            "employee_id": user.id,
            "full_name": user.full_name,
            "department_name": user.department_name,
            "total_seconds": sum(day["seconds"] for day in day_rows),
            "days": day_rows,
        })
    return {"date_from": date_from, "date_to": date_to, "days": _dates(date_from, date_to), "employees": employees}
