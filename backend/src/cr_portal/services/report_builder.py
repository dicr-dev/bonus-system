import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.models.reporting import DealStageHistory, ReportField
from cr_portal.models.task import BitrixTask


BASE_FIELDS: dict[str, dict[str, str]] = {
    "deals": {"bitrix_id": "ID сделки", "title": "Название сделки", "funnel": "Воронка", "stage_title": "Стадия", "status": "Статус", "opportunity": "Сумма", "created_time": "Создана", "closed_time": "Закрыта"},
    "tasks": {"bitrix_id": "ID задачи", "title": "Название задачи", "status": "Статус", "responsible_bitrix_id": "Исполнитель", "creator_bitrix_id": "Постановщик", "created_time": "Создана", "deadline": "Крайний срок", "closed_time": "Закрыта"},
    "stage_history": {"bitrix_event_id": "ID события", "stage_id": "Код стадии", "stage_title": "Стадия", "semantic": "Семантика", "occurred_at": "Дата перехода"},
}


def _value(value: Any) -> Any:
    if isinstance(value, (datetime, Decimal)):
        return str(value)
    return value


def _raw_row(item: Any, source: str) -> dict[str, Any]:
    row = {code: _value(getattr(item, code, None)) for code in BASE_FIELDS[source]}
    raw = getattr(item, "raw_json", None)
    if raw:
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                row.update({f"raw.{key}": _value(value) for key, value in payload.items()})
        except json.JSONDecodeError:
            pass
    return row


async def refresh_report_fields(session: AsyncSession) -> int:
    """Register stable fields and all keys currently present in local snapshots."""
    fields = {source: dict(values) for source, values in BASE_FIELDS.items()}
    for source, model in (("deals", Deal), ("tasks", BitrixTask)):
        for raw in (await session.execute(select(model.raw_json))).scalars():
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                fields[source].update({f"raw.{key}": key for key in payload})
    existing = {(item.entity_type, item.code): item for item in (await session.execute(select(ReportField))).scalars()}
    count = 0
    for source, items in fields.items():
        for code, title in items.items():
            if (source, code) not in existing:
                session.add(ReportField(entity_type=source, code=code, title=title))
                count += 1
    await session.commit()
    return count


def _matches(row: dict[str, Any], filters: list[dict[str, Any]]) -> bool:
    for item in filters:
        value, expected, op = row.get(str(item.get("field"))), item.get("value"), item.get("op", "eq")
        if op == "eq" and str(value) != str(expected): return False
        if op == "contains" and str(expected).lower() not in str(value).lower(): return False
        if op == "empty" and value not in (None, "", []): return False
        if op == "not_empty" and value in (None, "", []): return False
    return True


async def run_report(session: AsyncSession, source: str, config: dict[str, Any]) -> dict[str, Any]:
    models = {"deals": Deal, "tasks": BitrixTask, "stage_history": DealStageHistory}
    if source not in models:
        raise ValueError("Unsupported report source")
    rows = [_raw_row(item, source) for item in (await session.execute(select(models[source]))).scalars()]
    rows = [row for row in rows if _matches(row, config.get("filters", []))]
    selected = config.get("fields") or list(BASE_FIELDS[source])
    groups = config.get("group_by", [])
    if groups:
        grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows: grouped.setdefault(tuple(row.get(field) for field in groups), []).append(row)
        result = []
        for key, items in grouped.items():
            result.append({**dict(zip(groups, key)), "count": len(items), "sum": sum(float(item.get(config.get("sum_field"), 0) or 0) for item in items) if config.get("sum_field") else None})
        rows = result
    else:
        rows = [{field: row.get(field) for field in selected} for row in rows]
    for order in reversed(config.get("sort", [])):
        field, direction = order.get("field"), order.get("direction", "asc")
        rows.sort(key=lambda row: (row.get(field) is None, str(row.get(field, ""))), reverse=direction == "desc")
    return {"source": source, "fields": selected, "rows": rows[:10000], "total": len(rows), "truncated": len(rows) > 10000}
