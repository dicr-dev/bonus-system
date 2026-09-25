import json
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.task import BitrixTask, BitrixTaskElapsedItem
from cr_portal.models.user import User
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.employee_scope import employee_is_in_department
from cr_portal.services.kpi import next_month
from cr_portal.services.task_kpi import (
    crm_deal_ids,
    elapsed_items_between,
    field_value,
    parse_datetime,
    tasks_by_id,
)


def shift_month(month: date, offset: int) -> date:
    month_index = month.year * 12 + month.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def task_sync_window(
    now: datetime | None = None,
    *,
    months: int = 2,
    timezone_name: str = "Europe/Moscow",
) -> tuple[date, date]:
    local_now = (now or datetime.now(UTC)).astimezone(ZoneInfo(timezone_name))
    current_month = date(local_now.year, local_now.month, 1)
    return shift_month(current_month, -(months - 1)), next_month(current_month)


def _integer(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _seconds(value: Any) -> int:
    try:
        return max(0, int(Decimal(str(value or 0))))
    except (InvalidOperation, ValueError):
        return 0


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _is_empty_task_field(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)):
        return not any(str(item).strip() for item in value if item is not None)
    return not str(value).strip()


def _apply_task_snapshot(task: BitrixTask, payload: dict[str, Any], started_at: datetime) -> None:
    task.title = str(field_value(payload, "TITLE") or f"Задача #{task.bitrix_id}")
    task.responsible_bitrix_id = _integer(field_value(payload, "RESPONSIBLE_ID"))
    task.creator_bitrix_id = _integer(field_value(payload, "CREATED_BY"))
    task.group_id = _integer(field_value(payload, "GROUP_ID"))
    task.status = _integer(field_value(payload, "STATUS"))
    task.crm_deal_ids_json = _json(crm_deal_ids(payload))
    task.raw_json = _json(payload)
    task.created_time = parse_datetime(field_value(payload, "CREATED_DATE"))
    task.start_time = parse_datetime(field_value(payload, "DATE_START"))
    task.updated_time = parse_datetime(field_value(payload, "CHANGED_DATE"))
    task.deadline = parse_datetime(field_value(payload, "DEADLINE"))
    task.closed_time = parse_datetime(field_value(payload, "CLOSED_DATE"))
    task.synced_at = started_at


async def _relevant_task_ids(
    client: BitrixClient,
    session: AsyncSession,
    start_date: date,
    end_date: date,
    elapsed_items: list[dict],
    *,
    include_auxiliary_tasks: bool = True,
) -> tuple[list[str], list[str]]:
    business = await get_business_settings(session)
    start = start_date.isoformat() + "T00:00:00+03:00"
    end = end_date.isoformat() + "T00:00:00+03:00"
    ids = {
        str(task_id)
        for item in elapsed_items
        if (task_id := _integer(field_value(item, "TASK_ID"))) is not None
    }
    extra_select = [
        "CREATED_BY",
        "CREATED_DATE",
        "DATE_START",
        "CHANGED_DATE",
        "DEADLINE",
        "CLOSED_DATE",
        "STATUS",
        "TIME_SPENT_IN_LOGS",
    ]

    if include_auxiliary_tasks and business.task_training_bonus_field and business.task_training_yes_value:
        date_field = business.task_training_date_field or "DEADLINE"
        training_tasks = await client.call_all(
            "tasks.task.list",
            {
                "filter": {
                    business.task_training_bonus_field: business.task_training_yes_value,
                    f">={date_field}": start,
                    f"<{date_field}": end,
                },
                "select": ["ID", business.task_training_bonus_field, date_field],
                "order": {"ID": "ASC"},
            },
        )
        ids.update(
            str(task_id)
            for task in training_tasks
            if (task_id := _integer(field_value(task, "ID"))) is not None
        )
        extra_select.append(business.task_training_bonus_field)

    if include_auxiliary_tasks and business.overtime_project_id:
        overtime_tasks = await client.call_all(
            "tasks.task.list",
            {
                "filter": {
                    "GROUP_ID": business.overtime_project_id,
                    ">=DEADLINE": start,
                    "<DEADLINE": end,
                },
                "select": ["ID", "DEADLINE"],
                "order": {"ID": "ASC"},
            },
        )
        ids.update(
            str(task_id)
            for task in overtime_tasks
            if (task_id := _integer(field_value(task, "ID"))) is not None
        )
        if business.task_overtime_hours_field:
            extra_select.append(business.task_overtime_hours_field)

    return sorted(ids, key=int), list(dict.fromkeys(extra_select))


async def sync_tasks(
    session: AsyncSession,
    client: BitrixClient,
    *,
    months: int = 2,
    timezone_name: str = "Europe/Moscow",
    now: datetime | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    include_auxiliary_tasks: bool = True,
) -> dict[str, int | str]:
    """Cache KPI-relevant tasks and time entries for recent calculation months."""
    started_at = datetime.now(UTC)
    if start_date is None or end_date is None:
        start_date, end_date = task_sync_window(now, months=months, timezone_name=timezone_name)
    elapsed_items = await elapsed_items_between(client, start_date, end_date)
    task_ids, extra_select = await _relevant_task_ids(
        client,
        session,
        start_date,
        end_date,
        elapsed_items,
        include_auxiliary_tasks=include_auxiliary_tasks,
    )
    tasks = await tasks_by_id(client, task_ids, extra_select=extra_select)

    # Keep elapsed entries even if Bitrix no longer returns the task details.
    for task_id in task_ids:
        tasks.setdefault(task_id, {"ID": task_id, "TITLE": "Название задачи недоступно в Bitrix"})

    numeric_task_ids = [int(task_id) for task_id in task_ids]
    existing_tasks = {
        item.bitrix_id: item
        for item in (
            await session.execute(
                select(BitrixTask).where(BitrixTask.bitrix_id.in_(numeric_task_ids))
            )
        ).scalars()
    } if numeric_task_ids else {}

    for task_id, payload in tasks.items():
        numeric_id = int(task_id)
        task = existing_tasks.get(numeric_id)
        if task is None:
            task = BitrixTask(bitrix_id=numeric_id, title="")
            session.add(task)
        _apply_task_snapshot(task, payload, started_at)

    await session.flush()

    elapsed_ids = [
        elapsed_id
        for item in elapsed_items
        if (elapsed_id := _integer(field_value(item, "ID"))) is not None
    ]
    existing_elapsed = {
        item.bitrix_id: item
        for item in (
            await session.execute(
                select(BitrixTaskElapsedItem).where(
                    BitrixTaskElapsedItem.bitrix_id.in_(elapsed_ids)
                )
            )
        ).scalars()
    } if elapsed_ids else {}

    stored_elapsed = 0
    for payload in elapsed_items:
        elapsed_id = _integer(field_value(payload, "ID"))
        task_id = _integer(field_value(payload, "TASK_ID"))
        user_id = _integer(field_value(payload, "USER_ID"))
        created_time = parse_datetime(field_value(payload, "CREATED_DATE"))
        if elapsed_id is None or task_id is None or user_id is None or created_time is None:
            continue
        item = existing_elapsed.get(elapsed_id)
        if item is None:
            item = BitrixTaskElapsedItem(
                bitrix_id=elapsed_id,
                task_bitrix_id=task_id,
                user_bitrix_id=user_id,
                seconds=0,
                created_time=created_time,
            )
            session.add(item)
        item.task_bitrix_id = task_id
        item.user_bitrix_id = user_id
        item.seconds = _seconds(field_value(payload, "SECONDS"))
        item.created_time = created_time
        item.raw_json = _json(payload)
        item.synced_at = started_at
        stored_elapsed += 1

    start_time = datetime.combine(start_date, datetime.min.time(), ZoneInfo(timezone_name)).astimezone(UTC)
    end_time = datetime.combine(end_date, datetime.min.time(), ZoneInfo(timezone_name)).astimezone(UTC)
    await session.execute(
        delete(BitrixTaskElapsedItem).where(
            BitrixTaskElapsedItem.created_time >= start_time,
            BitrixTaskElapsedItem.created_time < end_time,
            BitrixTaskElapsedItem.synced_at < started_at,
        )
    )
    await session.commit()

    return {
        "tasks": len(tasks),
        "elapsed_items": stored_elapsed,
        "period_from": start_date.isoformat(),
        "period_to": end_date.isoformat(),
    }


async def sync_task_1c_errors(
    session: AsyncSession,
    client: BitrixClient,
) -> dict[str, int]:
    """Cache 1C developers' tasks for validation of the project and type field."""
    business = await get_business_settings(session)
    type_field = business.task_1c_type_field
    if not type_field:
        return {"task_1c_errors_tasks": 0, "task_1c_errors": 0}

    responsible_users = [
        user.bitrix_id
        for user in (await session.execute(select(User).where(User.is_active.is_(True)))).scalars()
        if employee_is_in_department(user, "Разработка 1С")
    ]
    if not responsible_users:
        return {"task_1c_errors_tasks": 0, "task_1c_errors": 0}

    payloads: list[dict] = []
    select_fields = [
        "ID", "TITLE", "RESPONSIBLE_ID", "CREATED_BY", "GROUP_ID", "STATUS",
        "CREATED_DATE", "DATE_START", "CHANGED_DATE", "DEADLINE", "CLOSED_DATE",
        "UF_CRM_TASK", type_field,
    ]
    for responsible_id in responsible_users:
        payloads.extend(await client.call_all("tasks.task.list", {
            "filter": {"RESPONSIBLE_ID": responsible_id},
            "select": select_fields,
            "order": {"ID": "ASC"},
        }))

    task_ids = [
        task_id for payload in payloads
        if (task_id := _integer(field_value(payload, "ID"))) is not None
    ]
    existing = {
        task.bitrix_id: task
        for task in (await session.execute(select(BitrixTask).where(BitrixTask.bitrix_id.in_(task_ids)))).scalars()
    } if task_ids else {}
    started_at = datetime.now(UTC)
    errors = 0
    for payload in payloads:
        task_id = _integer(field_value(payload, "ID"))
        if task_id is None:
            continue
        task = existing.get(task_id)
        if task is None:
            task = BitrixTask(bitrix_id=task_id, title="")
            session.add(task)
        _apply_task_snapshot(task, payload, started_at)
        task.task_1c_type_missing = _is_empty_task_field(field_value(payload, type_field))
        errors += int(task.task_1c_type_missing)

    await session.commit()
    return {"task_1c_errors_tasks": len(payloads), "task_1c_errors": errors}
