"""Read task KPI inputs; calculation items preserve the resulting snapshot."""
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from cr_portal.services.kpi import next_month


def field_value(task: dict, field: str):
    key = field.replace("_", "").lower()
    return next((v for k, v in task.items() if k.replace("_", "").lower() == key), None)


def in_month(value, month: date) -> bool:
    if not value:
        return False
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo:
        parsed = parsed.astimezone(ZoneInfo("Europe/Moscow"))
    return month <= parsed.date() < next_month(month)


def parse_datetime(value) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Moscow"))
    return parsed.astimezone(UTC)


def positive_decimal(value) -> Decimal:
    try:
        number = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Некорректное количество часов в задаче") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Количество часов должно быть неотрицательным числом")
    return number


def overtime_hours(task: dict, config) -> tuple[Decimal, str]:
    manual = field_value(task, config.task_overtime_hours_field) if config.task_overtime_hours_field else None
    tracker = field_value(task, "TIME_SPENT_IN_LOGS")
    if manual not in (None, "") and (config.overtime_time_priority == "manual" or tracker in (None, "")):
        return positive_decimal(manual), "manual"
    return positive_decimal(tracker or 0) / Decimal(3600), "tracker"


async def elapsed_items_between(client, start_date: date, end_date: date) -> list[dict]:
    """Read timer entries in a half-open Moscow date range."""
    start = start_date.isoformat() + "T00:00:00+03:00"
    end = end_date.isoformat() + "T00:00:00+03:00"
    result: list[dict] = []
    page = 1
    while True:
        response = await client.call("task.elapseditem.getlist", {
            "TASKID": 0,
            "ORDER": {"ID": "asc"},
            "FILTER": {">=CREATED_DATE": start, "<CREATED_DATE": end},
            "SELECT": ["ID", "TASK_ID", "USER_ID", "SECONDS", "CREATED_DATE"],
            "PARAMS": {"NAV_PARAMS": {"nPageSize": 50, "iNumPage": page}},
        })
        batch = response.get("result", [])
        result.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    return result


async def elapsed_items_in_month(client, month: date) -> list[dict]:
    """Read all timer entries for the month using elapsed-item page numbers."""
    return await elapsed_items_between(client, month, next_month(month))


async def tasks_by_id(
    client,
    task_ids: list[str],
    extra_select: list[str] | None = None,
) -> dict[str, dict]:
    select = ["ID", "TITLE", "RESPONSIBLE_ID", "GROUP_ID", "UF_CRM_TASK"]
    for field in extra_select or []:
        if field and field not in select:
            select.append(field)
    result: dict[str, dict] = {}
    for offset in range(0, len(task_ids), 50):
        response = await client.call("tasks.task.list", {
            "filter": {"ID": task_ids[offset:offset + 50]},
            "select": select,
            "order": {"ID": "asc"},
        })
        for task in response.get("result", {}).get("tasks", []):
            result[str(field_value(task, "ID"))] = task
    return result


def crm_deal_ids(task: dict) -> list[int]:
    values = field_value(task, "UF_CRM_TASK") or []
    if not isinstance(values, list):
        values = [values]
    result = []
    for value in values:
        raw = str(value).strip()
        if raw.upper().startswith("D_") and raw[2:].isdigit():
            result.append(int(raw[2:]))
    return result


def support_deal_allows_time(support, implementations: list, logged_at: datetime) -> bool:
    created_at = parse_datetime(support.created_time)
    if created_at and logged_at < created_at:
        return False
    if support.status == "lost":
        closed_at = parse_datetime(support.closed_time or support.updated_time)
        if closed_at and logged_at > closed_at:
            return False
    # The established current-client rule allows an active support deal when
    # its implementation link is missing; diagnostics reports the data issue.
    if not implementations:
        return True
    return any(
        implementation.status == "won"
        and (closed_at := parse_datetime(implementation.closed_time or implementation.updated_time))
        and closed_at <= logged_at
        for implementation in implementations
    )


async def support_hour_contributions(
    client,
    month,
    users,
    rules,
    support_deals,
    implementations_by_support,
    reference_deals=None,
):
    """Aggregate task time; only eligible support tasks produce a bonus."""
    logs = await elapsed_items_in_month(client, month)
    task_ids = list(dict.fromkeys(str(item.get("TASK_ID")) for item in logs if item.get("TASK_ID")))
    tasks = await tasks_by_id(client, task_ids)
    users_by_bitrix_id = {str(user.bitrix_id): user.id for user in users}
    support_by_bitrix_id = {deal.bitrix_id: deal for deal in support_deals}
    reference_by_bitrix_id = {
        deal.bitrix_id: deal for deal in (reference_deals or [])
    }
    aggregated: dict[tuple, dict] = {}

    for log in logs:
        task_id = str(log.get("TASK_ID") or "")
        task = tasks.get(task_id)
        employee_id = users_by_bitrix_id.get(str(log.get("USER_ID") or ""))
        logged_at = parse_datetime(log.get("CREATED_DATE"))
        seconds = int(positive_decimal(log.get("SECONDS") or 0))
        if not task or employee_id is None or logged_at is None or seconds <= 0:
            continue

        deal_ids = crm_deal_ids(task)
        support = next(
            (
                support_by_bitrix_id[deal_id]
                for deal_id in deal_ids
                if deal_id in support_by_bitrix_id
                and support_deal_allows_time(
                    support_by_bitrix_id[deal_id],
                    implementations_by_support.get(support_by_bitrix_id[deal_id].id, []),
                    logged_at,
                )
            ),
            None,
        )
        deal = support
        if deal is None:
            deal = next(
                (
                    reference_by_bitrix_id[deal_id]
                    for deal_id in deal_ids
                    if deal_id in reference_by_bitrix_id
                ),
                None,
            )
        if deal is None:
            continue

        key = (employee_id, task_id, deal.id)
        entry = aggregated.setdefault(key, {
            "employee_id": employee_id,
            "task_id": task_id,
            "task": task,
            "deal": deal,
            "calculated": support is not None,
            "seconds": 0,
            "elapsed_ids": [],
        })
        entry["seconds"] += seconds
        entry["elapsed_ids"].append(str(log.get("ID")))

    support_rate = Decimal(str(rules["support_hour_rate"]))
    result = []
    for entry in aggregated.values():
        hours = (Decimal(entry["seconds"]) / Decimal(3600)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        calculated = entry["calculated"]
        rate = support_rate if calculated else Decimal("0")
        before = (
            (hours * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if calculated
            else Decimal("0")
        )
        bonus_type = "support_hours" if calculated else "task_hours_reference"
        task_title = field_value(entry["task"], "TITLE") or f"Задача {entry['task_id']}"
        result.append((entry["employee_id"], (
            entry["deal"], bonus_type, rate, rate, hours, before, calculated,
            (
                f"Часы сопровождения: {task_title} — {hours} ч × {rate} ₽"
                if calculated
                else f"Справочные часы: {task_title} — {hours} ч"
            ),
            {
                "task_id": entry["task_id"],
                "task": entry["task"],
                "client_deal_funnel": getattr(entry["deal"], "funnel", "support"),
                "elapsed_ids": entry["elapsed_ids"],
                "seconds": entry["seconds"],
                "hours_source": "elapsed_items",
            },
        )))
    return result


async def task_contributions(
    client,
    config,
    month,
    users,
    rules,
    support_deals=None,
    implementations_by_support=None,
    reference_deals=None,
):
    result = []
    user_map = {str(u.bitrix_id): u.id for u in users}
    start = month.isoformat() + "T00:00:00+03:00"
    end = next_month(month).isoformat() + "T00:00:00+03:00"
    select = ["ID", "TITLE", "RESPONSIBLE_ID", "DEADLINE", "CLOSED_DATE", "GROUP_ID", "TIME_SPENT_IN_LOGS"]
    if config.task_training_bonus_field:
        yes = config.task_training_yes_value
        if not yes:
            raise ValueError("Укажите значение «Да» для поля бонуса за обучение в настройках")
        date_field = config.task_training_date_field
        tasks = await client.call_all("tasks.task.list", {
            "filter": {config.task_training_bonus_field: yes, ">=" + date_field: start, "<" + date_field: end},
            "select": select + [config.task_training_bonus_field], "order": {"ID": "ASC"},
        })
        seen = set()
        for task in tasks:
            task_id = str(field_value(task, "ID"))
            employee = user_map.get(str(field_value(task, "RESPONSIBLE_ID")))
            if task_id in seen or not in_month(field_value(task, date_field), month):
                continue
            seen.add(task_id)
            if str(field_value(task, config.task_training_bonus_field)) != yes:
                continue
            if employee is None:
                raise ValueError(f"Исполнитель задачи {task_id} не синхронизирован")
            rate = Decimal(str(rules["training_bonus"]))
            result.append((employee, (None, "training", rate, rate, Decimal(1), rate, True,
                f"Обучение: {field_value(task, 'TITLE')}", {"task_id": task_id, "task": task, "date_field": date_field})))

    if config.overtime_project_id:
        departments = [v.strip() for v in config.overtime_department_ids.split(",") if v.strip()]
        if not departments:
            raise ValueError("Укажите отделы исполнителей переработок в настройках")
        eligible = set()
        for department in departments:
            members = await client.call_all("user.get", {"FILTER": {"UF_DEPARTMENT": department}})
            eligible.update(str(u["ID"]) for u in members)
        tasks = await client.call_all("tasks.task.list", {
            "filter": {"GROUP_ID": config.overtime_project_id, ">=DEADLINE": start, "<DEADLINE": end},
            "select": select + ([config.task_overtime_hours_field] if config.task_overtime_hours_field else []),
            "order": {"ID": "ASC"},
        })
        seen = set()
        for task in tasks:
            task_id = str(field_value(task, "ID"))
            responsible = str(field_value(task, "RESPONSIBLE_ID"))
            if task_id in seen or responsible not in eligible or not in_month(field_value(task, "DEADLINE"), month):
                continue
            if str(field_value(task, "GROUP_ID")) != str(config.overtime_project_id):
                continue
            seen.add(task_id)
            if responsible not in user_map:
                raise ValueError(f"Исполнитель задачи {task_id} не синхронизирован")
            hours, source = overtime_hours(task, config)
            result.append((user_map[responsible], (None, "overtime_hours", Decimal(0), Decimal(0), hours,
                Decimal(0), False, f"Переработки: {field_value(task, 'TITLE')} — {hours} ч",
                {"task_id": task_id, "task": task, "hours_source": source, "hours_only": True})))
    if support_deals is not None:
        result.extend(await support_hour_contributions(
            client,
            month,
            users,
            rules,
            support_deals,
            implementations_by_support or {},
            reference_deals or [],
        ))
    return result
