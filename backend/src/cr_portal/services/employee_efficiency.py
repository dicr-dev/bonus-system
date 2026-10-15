from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import select

from cr_portal.models.deal import Deal
from cr_portal.models.reporting import DealStageHistory
from cr_portal.models.user import User
from cr_portal.services.bonus import raw_date
from cr_portal.services.deal_analytics import matching_source_ids
from cr_portal.services.employee_scope import employee_is_in_department

MOSCOW = ZoneInfo("Europe/Moscow")
FUNNELS = ("tech_integration", "implementation")
SEMANTICS = {"P": "in_progress", "S": "won", "F": "lost"}
TRAININGS = ("first", "second", "reports")


def _aware(value):
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _in_period(value, start, end):
    value = _aware(value)
    return value is not None and (start is None or value >= start) and value < end


def _training_target(module):
    module = str(module or "").strip().casefold()
    if module in {"логистика", "эксплуатация"}:
        return 3
    if module in {"топливный модуль", "тм", "загрузки"}:
        return 1
    return None


def _state_at(deal, events, boundary):
    """State immediately before boundary; terminal-stage edits keep closure date."""
    if events:
        status, closed, reason = "in_progress", None, None
        for event in events:
            occurred = _aware(event.occurred_at)
            if occurred >= boundary:
                break
            next_status = SEMANTICS.get(str(event.semantic or "").upper())
            if next_status is None:
                continue
            if next_status in {"won", "lost"}:
                if status != next_status:
                    closed = occurred
            else:
                closed = None
            status = next_status
            reason = event.stage_title
        return status, closed, reason
    closed = _aware(deal.closed_time)
    if closed is not None and closed >= boundary:
        return "in_progress", None, None
    if deal.status in {"won", "lost"} and closed is None:
        return "unknown", None, deal.stage_title
    return deal.status, closed, deal.stage_title


def _days(start, end):
    start, end = _aware(start), _aware(end)
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds() / 86400, 1)


def _metrics(rows):
    won = [row for row in rows if row["won_in_period"]]
    lost = [row for row in rows if row["lost_in_period"]]
    durations = [row["duration_days"] for row in won if row["duration_days"] is not None]
    with_1c = [row["duration_days"] for row in won if row["integration_1c"] and row["duration_days"] is not None]
    without_1c = [row["duration_days"] for row in won if not row["integration_1c"] and row["duration_days"] is not None]
    return {
        "deal_count": len(rows),
        "new_count": sum(row["new_in_period"] for row in rows),
        "work_count": sum(row["worked_in_period"] for row in rows),
        "active_end_count": sum(row["status_at_end"] == "in_progress" for row in rows),
        "won_count": len(won), "lost_count": len(lost),
        "won_amount": str(sum((Decimal(row["amount"]) for row in won), Decimal(0))),
        "lost_amount": str(sum((Decimal(row["amount"]) for row in lost), Decimal(0))),
        "success_rate": round(len(won) * 100 / (len(won) + len(lost)), 1) if won or lost else None,
        "avg_completion_days": round(mean(durations), 1) if durations else None,
        "with_1c_count": sum(row["integration_1c"] for row in rows),
        "won_with_1c_count": sum(row["integration_1c"] for row in won),
        "avg_days_with_1c": round(mean(with_1c), 1) if with_1c else None,
        "avg_days_without_1c": round(mean(without_1c), 1) if without_1c else None,
        "training_count": sum(len(row["trainings_in_period"]) for row in rows),
        **{f"{name}_training_count": sum(name in row["trainings_in_period"] for row in rows) for name in TRAININGS},
        "fully_trained_count": sum(row["training_target"] is not None and row["training_done"] >= row["training_target"] for row in rows),
        "unknown_training_target_count": sum(row["funnel"] == "implementation" and row["training_target"] is None for row in rows),
        "support_created_count": sum(len(row["supports_created_in_period"]) for row in rows),
    }


def _funnel_metrics(rows):
    return {funnel: _metrics([row for row in rows if row["funnel"] == funnel]) for funnel in FUNNELS}


def _losses(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["lost_in_period"]:
            groups[(row["funnel"], row["loss_reason"] or "Причина не указана")].append(row)
    return [{"funnel": funnel, "reason": reason, "count": len(items),
             "amount": str(sum((Decimal(item["amount"]) for item in items), Decimal(0)))}
            for (funnel, reason), items in sorted(groups.items())]


def build_employee_efficiency(deals, users, histories, business, *, date_from=None, date_to=None,
                              employee_id=None, module=None, integration_1c=None, now=None):
    now = _aware(now or datetime.now(UTC))
    today = now.astimezone(MOSCOW).date()
    if date_to and date_to > today:
        raise ValueError("Дата окончания не может быть позже сегодняшнего дня")
    if date_from and date_from > (date_to or today):
        raise ValueError("Дата начала не может быть позже даты окончания")
    end_date = (date_to or today) + timedelta(days=1)
    start = datetime.combine(date_from, time.min, MOSCOW) if date_from else None
    end = min(datetime.combine(end_date, time.min, MOSCOW), now)
    core = [deal for deal in deals if deal.funnel in FUNNELS]
    tech = {deal.bitrix_id: deal for deal in core if deal.funnel == "tech_integration"}
    implementations = {deal.bitrix_id: deal for deal in core if deal.funnel == "implementation"}
    supports = defaultdict(list)
    for support in deals:
        if support.funnel == "support":
            for parent in matching_source_ids(support, business.field_source_deal_id, implementations):
                supports[parent].append(support)
    user_map = {user.id: user for user in users}
    events_by_deal = defaultdict(list)
    for event in histories:
        if SEMANTICS.get(str(event.semantic or "").upper()):
            events_by_deal[event.deal_id].append(event)
    for events in events_by_deal.values():
        events.sort(key=lambda event: (_aware(event.occurred_at), event.bitrix_event_id))
    rows = []
    missing_history = missing_closed = invalid_dates = 0
    for deal in core:
        owner = str(deal.implementation_responsible_user_id) if deal.implementation_responsible_user_id else "unassigned"
        if employee_id and owner != str(employee_id):
            continue
        if module and deal.module_name != module:
            continue
        effective_1c = bool(deal.integration_1c)
        if deal.funnel == "implementation":
            effective_1c = effective_1c or any(tech[parent].integration_1c for parent in matching_source_ids(deal, business.field_source_deal_id, tech))
        if integration_1c is not None and effective_1c != integration_1c:
            continue
        created = _aware(deal.created_time)
        if created is not None and created >= end:
            continue
        events = [event for event in events_by_deal[deal.id] if event.category_id in (None, deal.category_id)]
        status, closed, stage = _state_at(deal, events, end)
        born = _in_period(created, start, end)
        won = status == "won" and _in_period(closed, start, end)
        lost = status == "lost" and _in_period(closed, start, end)
        training_dates = {}
        target = _training_target(deal.module_name) if deal.funnel == "implementation" else None
        if deal.funnel == "implementation":
            for name, field in zip(TRAININGS, (business.field_first_training_date, business.field_second_training_date, business.field_reports_training_date)):
                training_dates[name] = raw_date(deal, field)
        counted_trainings = TRAININGS[:1] if target == 1 else TRAININGS
        training_events = [name for name in counted_trainings if training_dates.get(name) is not None
                           and (date_from is None or training_dates[name] >= date_from)
                           and training_dates[name] <= (date_to or today)]
        before_end = sum(training_dates.get(name) is not None and training_dates[name] <= (date_to or today) for name in counted_trainings)
        new_supports = [support.bitrix_id for support in supports[deal.bitrix_id] if _in_period(support.created_time, start, end)]
        if start is None:
            worked = True
        elif events:
            worked = born or _state_at(deal, events, start)[0] == "in_progress" or any(
                _in_period(event.occurred_at, start, end) and SEMANTICS.get(str(event.semantic).upper()) == "in_progress" for event in events
            ) or won or lost
        else:
            worked = born or status == "in_progress" or (closed is not None and closed >= start)
        if not (born or worked or won or lost or training_events or new_supports):
            continue
        missing_history += not bool(events)
        missing_closed += status == "unknown"
        duration = _days(created, closed or end)
        invalid_dates += created is None or duration is None
        last_event = next((event for event in reversed(events) if _aware(event.occurred_at) < end), None)
        person = user_map.get(deal.implementation_responsible_user_id)
        rows.append({
            "id": str(deal.id), "bitrix_id": deal.bitrix_id, "title": deal.title,
            "employee_id": owner, "employee_name": person.full_name if person else "Без ответственного за внедрение" if owner == "unassigned" else "Несинхронизированный сотрудник",
            "funnel": deal.funnel, "module_name": deal.module_name or "Модуль не указан",
            "integration_1c": effective_1c, "amount": str(deal.opportunity or 0),
            "created_at": created.isoformat() if created else None,
            "closed_at": closed.isoformat() if closed else None,
            "status_at_end": status, "current_status": deal.status,
            "stage_title": stage or deal.stage_title, "current_stage_title": deal.stage_title,
            "new_in_period": born, "worked_in_period": worked,
            "won_in_period": won, "lost_in_period": lost,
            "loss_reason": stage or deal.stage_title if lost else None,
            "duration_days": duration,
            "days_in_stage": _days(last_event.occurred_at, end) if last_event else None,
            "training_dates": {name: value.isoformat() if value else None for name, value in training_dates.items()},
            "training_target": target, "training_done": before_end,
            "trainings_in_period": training_events, "supports_created_in_period": new_supports,
            "history_available": bool(events),
            "history": [{"at": _aware(event.occurred_at).isoformat(), "stage": event.stage_title or event.stage_id,
                         "status": SEMANTICS.get(str(event.semantic).upper())} for event in events],
        })
    owners = {row["employee_id"] for row in rows}
    owners.update(str(user.id) for user in users if employee_is_in_department(user, "Отдел внедрения") and user.is_active
                  and (employee_id is None or str(user.id) == str(employee_id)))
    people = {str(user.id): user for user in users}
    employees = []
    for owner in owners:
        employee_rows = sorted([row for row in rows if row["employee_id"] == owner], key=lambda row: (row["funnel"], row["bitrix_id"]))
        person = people.get(owner)
        name = person.full_name if person else "Без ответственного за внедрение" if owner == "unassigned" else "Несинхронизированный сотрудник"
        employees.append({
            "id": owner, "name": name, "department": person.department_name if person else None,
            "is_active": person.is_active if person else None,
            "metrics": _funnel_metrics(employee_rows), "deals": employee_rows,
            "modules": [{"module_name": name, "metrics": _funnel_metrics([row for row in employee_rows if row["module_name"] == name])}
                        for name in sorted({row["module_name"] for row in employee_rows})],
        })
    employees.sort(key=lambda person: person["name"])
    warnings = []
    if missing_history:
        warnings.append(f"У {missing_history} сделок не загружена история стадий. Их состояние на конец периода восстановлено приближённо по датам создания и закрытия.")
    if missing_closed:
        warnings.append(f"У {missing_closed} закрытых сделок нет даты закрытия: они не включены в успешные и неуспешные закрытия периода.")
    if invalid_dates:
        warnings.append(f"У {invalid_dates} сделок отсутствуют или некорректны даты для расчёта длительности.")
    unknown_modules = sorted({row["module_name"] for row in rows if row["funnel"] == "implementation" and row["training_target"] is None})
    if unknown_modules:
        warnings.append("Норматив числа обучений не определён для модулей: " + ", ".join(unknown_modules) + ". Показываются только фактические даты.")
    return {
        "date_from": date_from.isoformat() if date_from else None, "date_to": (date_to or today).isoformat(),
        "generated_at": now.isoformat(), "summary": _funnel_metrics(rows),
        "employees": employees, "losses": _losses(rows), "warnings": warnings,
        "history_deals": len(rows) - missing_history, "total_deals": len(rows),
        "options": {"modules": sorted({deal.module_name for deal in core if deal.module_name}),
                    "employees": [{"id": str(user.id), "name": user.full_name} for user in sorted(users, key=lambda item: item.full_name)
                                  if user.id in {deal.implementation_responsible_user_id for deal in core} or employee_is_in_department(user, "Отдел внедрения")]},
    }


async def employee_efficiency_report(session, business, **filters):
    deals = list((await session.execute(select(Deal).where(Deal.funnel.in_((*FUNNELS, "support"))))).scalars())
    users = list((await session.execute(select(User))).scalars())
    histories = list((await session.execute(select(DealStageHistory).where(
        DealStageHistory.deal_id.in_([deal.id for deal in deals if deal.funnel in FUNNELS])
    ))).scalars()) if deals else []
    return build_employee_efficiency(deals, users, histories, business, **filters)
