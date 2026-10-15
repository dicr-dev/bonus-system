"""Monthly employee rating. All business metrics use synchronized local data."""
import json
from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from cr_portal.models.app_settings import AppSetting
from cr_portal.models.deal import Deal
from cr_portal.models.task import BitrixTask, BitrixTaskElapsedItem
from cr_portal.models.user import User
from cr_portal.services.employee_scope import employee_is_in_department
from cr_portal.services.kpi import next_month
from cr_portal.services.task_kpi import field_value

MOSCOW = ZoneInfo("Europe/Moscow")
TYPE_LABEL = "Реализация интеграции"
TYPE_CACHE_KEY = "monthly_rating.task_type_metadata"


def month_bounds(month: str | None):
    value = month or datetime.now(MOSCOW).strftime("%Y-%m")
    try:
        parsed = date.fromisoformat(value + "-01")
        end = next_month(parsed)
        if parsed.strftime("%Y-%m") != value:
            raise ValueError
    except (ValueError, OverflowError) as error:
        raise ValueError("Месяц должен быть в формате ГГГГ-ММ (до 9999-11)") from error
    return value, datetime.combine(parsed, time.min, MOSCOW), datetime.combine(end, time.min, MOSCOW)


def _json(value, default):
    try:
        result = json.loads(value or "null")
        return result if isinstance(result, type(default)) else default
    except (TypeError, ValueError):
        return default


def _in_period(value, start, end):
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=MOSCOW)
    return start <= value < end


async def refresh_type_metadata(session, client, field):
    """Resolve portal enum IDs from official user-field metadata, never from task titles."""
    fields = await client.call_all("task.item.userfield.getlist", {"FILTER": {"FIELD_NAME": field}})
    descriptor = next((row for row in fields if field_value(row, "FIELD_NAME") == field), None)
    if descriptor is None:
        raise ValueError("Поле «Тип задачи 1С» не найдено в Битриксе")
    response = await client.call("task.item.userfield.get", {"ID": field_value(descriptor, "ID")})
    descriptor = response.get("result", {})
    options = field_value(descriptor, "LIST") if isinstance(descriptor, dict) else None
    labels = {
        str(field_value(item, "ID")): str(field_value(item, "VALUE"))
        for item in (options or []) if isinstance(item, dict) and field_value(item, "ID") is not None
    }
    if not any(label.strip().casefold() == TYPE_LABEL.casefold() for label in labels.values()):
        raise ValueError("В справочнике «Тип задачи 1С» нет значения «Реализация интеграции»")
    payload = {"field": field, "labels": labels, "loaded_at": datetime.now(MOSCOW).isoformat()}
    setting = await session.get(AppSetting, TYPE_CACHE_KEY)
    if setting is None:
        setting = AppSetting(key=TYPE_CACHE_KEY)
        session.add(setting)
    setting.value = json.dumps(payload, ensure_ascii=False)
    await session.commit()
    return payload


def _is_integration_task(task, field, labels):
    raw = _json(task.raw_json, {})
    value = field_value(raw, field)
    values = value if isinstance(value, list) else [value]
    return any(
        str(labels.get(str(item), item)).strip().casefold() == TYPE_LABEL.casefold()
        for item in values if item is not None
    )


def build_monthly_rating(users, deals, tasks, elapsed, *, month, type_field, labels=None):
    month, start, end = month_bounds(month)
    labels = labels or {}
    by_bitrix = {user.bitrix_id: user for user in users}
    implementers = {}
    developers = {}
    for user in users:
        if not user.is_active:
            continue
        base = {"id": str(user.id), "bitrix_id": user.bitrix_id, "name": user.full_name}
        if employee_is_in_department(user, "Отдел внедрения"):
            implementers[user.id] = {**base, "deal_count": 0, "deal_amount": Decimal(0), "deals": []}
        if employee_is_in_department(user, "Разработка 1С"):
            developers[user.bitrix_id] = {**base, "task_count": 0, "integration_count": 0, "seconds": 0}

    tasks_by_deal = {}
    unknown_type_count = 0
    for task in tasks:
        developer = developers.get(task.responsible_bitrix_id)
        if developer is not None and task.status == 5 and _in_period(task.closed_time, start, end):
            developer["task_count"] += 1
        # Integration tasks may have been completed outside the reporting month, or remain open.
        if not _is_integration_task(task, type_field, labels):
            value = field_value(_json(task.raw_json, {}), type_field)
            values = value if isinstance(value, list) else [value]
            unknown = any(v not in (None, "") and str(v) not in labels for v in values)
            if unknown:
                unknown_type_count += 1
            continue
        for deal_id in set(str(value) for value in _json(task.crm_deal_ids_json, [])):
            tasks_by_deal.setdefault(deal_id, []).append(task)

    for entry in elapsed:
        if (developer := developers.get(entry.user_bitrix_id)) is not None and _in_period(entry.created_time, start, end):
            developer["seconds"] += entry.seconds

    issues = []
    unattributed = 0
    for deal in deals:
        if deal.status != "won" or not _in_period(deal.closed_time, start, end):
            continue
        detail = {"bitrix_id": deal.bitrix_id, "title": deal.title, "amount": str(deal.opportunity or 0)}
        if deal.funnel == "implementation":
            if (person := implementers.get(deal.implementation_responsible_user_id)) is not None:
                person["deal_count"] += 1
                person["deal_amount"] += deal.opportunity or Decimal(0)
                person["deals"].append(detail)
            else:
                unattributed += 1
        if deal.funnel != "tech_integration" or not deal.integration_1c:
            continue
        linked = tasks_by_deal.get(str(deal.bitrix_id), [])
        owners = {task.responsible_bitrix_id for task in linked}
        reason = None
        if len(owners) > 1:
            reason = "Разные исполнители задач реализации интеграции — интеграция не засчитана"
        elif not linked:
            reason = "Не найдена задача с типом «Реализация интеграции»"
        elif next(iter(owners)) not in developers:
            reason = "Исполнитель не является действующим сотрудником отдела «Разработка 1С»"
        if reason:
            issues.append({**detail, "reason": reason, "tasks": [
                {"bitrix_id": task.bitrix_id, "title": task.title,
                 "responsible_bitrix_id": task.responsible_bitrix_id, "group_id": task.group_id,
                 "responsible_name": by_bitrix[task.responsible_bitrix_id].full_name
                 if task.responsible_bitrix_id in by_bitrix else "Неизвестный исполнитель"}
                for task in sorted(linked, key=lambda item: item.bitrix_id)
            ]})
        else:
            developers[next(iter(owners))]["integration_count"] += 1

    implementation = sorted(implementers.values(), key=lambda row: (-row["deal_amount"], row["name"].casefold()))
    for row in implementation:
        row["deal_amount"] = str(row["deal_amount"])
        row["deals"].sort(key=lambda deal: (-Decimal(deal["amount"]), deal["title"].casefold()))
    for row in developers.values():
        row["hours"] = str((Decimal(row.pop("seconds")) / 3600).quantize(Decimal("0.01")))
    warnings = []
    if not labels:
        warnings.append("Справочник «Тип задачи 1С» не загружен. Обновите его для достоверного подсчёта интеграций.")
    if unknown_type_count:
        warnings.append(f"Не распознаны значения типа у {unknown_type_count} задач. Обновите справочник.")
    if unattributed:
        warnings.append(f"Успешных Внедрений вне рейтинга действующих сотрудников отдела: {unattributed}.")
    warnings.append("Данные берутся из локальной синхронизации. Полнота отчёта зависит от загрузки сделок, задач и записей времени за выбранный месяц.")
    development = sorted(developers.values(), key=lambda row: (-row["integration_count"], row["name"].casefold()))
    reliable = bool(labels) and not unknown_type_count
    if not reliable:
        for row in development:
            row["integration_count"] = None
    return {"month": month, "implementation": implementation,
            "development": development,
            "integration_issues": sorted(issues, key=lambda row: row["bitrix_id"]),
            "integration_count_reliable": reliable, "warnings": warnings}


async def monthly_rating_report(session, business, month=None):
    month, start, end = month_bounds(month)
    users = (await session.execute(select(User))).scalars().all()
    deals = (await session.execute(select(Deal).where(
        Deal.funnel.in_(["implementation", "tech_integration"]), Deal.status == "won",
        Deal.closed_time >= start, Deal.closed_time < end,
    ))).scalars().all()
    # No month restriction: tasks identify the integration's developer for deals closed this month.
    tasks = (await session.execute(select(BitrixTask))).scalars().all()
    elapsed = (await session.execute(select(BitrixTaskElapsedItem).where(
        BitrixTaskElapsedItem.created_time >= start, BitrixTaskElapsedItem.created_time < end,
    ))).scalars().all()
    setting = await session.get(AppSetting, TYPE_CACHE_KEY)
    metadata = _json(setting.value if setting else None, {})
    labels = metadata.get("labels", {}) if metadata.get("field") == business.task_1c_type_field else {}
    result = build_monthly_rating(users, deals, tasks, elapsed, month=month,
                                  type_field=business.task_1c_type_field, labels=labels)
    result["type_metadata_loaded_at"] = metadata.get("loaded_at") if labels else None
    return result
