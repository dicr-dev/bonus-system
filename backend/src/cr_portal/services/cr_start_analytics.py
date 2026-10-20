"""CR Start portfolio, usage intervals and actual task effort (local data only)."""
import calendar
import json
from collections import defaultdict
from datetime import UTC, datetime, time
from decimal import Decimal
from statistics import mean, median
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import load_only

from cr_portal.models.deal import Deal
from cr_portal.models.reporting import DealStageHistory
from cr_portal.models.task import BitrixTask, BitrixTaskElapsedItem
from cr_portal.models.user import User
from cr_portal.services.bonus import raw_date
from cr_portal.services.cr_start_manager_report import _stage_group
from cr_portal.services.employee_scope import employee_is_in_department

MOSCOW = ZoneInfo("Europe/Moscow")
MODULES = ("Логистика", "Топливный модуль", "Эксплуатация")


def aware(value):
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def iso(value):
    return aware(value).astimezone(MOSCOW).isoformat() if value else None


def number(value):
    return round(float(value), 2) if value is not None else None


def add_months(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    return value.replace(year=year, month=month + 1,
                         day=min(value.day, calendar.monthrange(year, month + 1)[1]))


def module_name(deal):
    # module_name is the enum label normalized by deal synchronization, not its Bitrix enum ID.
    return {"кр старт тм": "Топливный модуль", "кр старт эксплуатация": "Эксплуатация"}.get(
        " ".join((deal.module_name or "").split()).casefold(), "Логистика")


def task_deal_ids(task):
    try:
        values = json.loads(task.crm_deal_ids_json or "[]")
        if not isinstance(values, list):
            return None
        return sorted({int(value) for value in values})
    except (ValueError, TypeError):
        return None


def usage_timeline(deal, history, first_date, now):
    """Only explicit field/history dates; never infer churn from card modification time."""
    now = aware(now)
    first = datetime.combine(first_date, time.min, MOSCOW) if first_date else None
    created = aware(deal.created_time)
    events = sorted([event for event in history if aware(event.occurred_at) <= now
                     and event.category_id in (None, deal.category_id)],
                    key=lambda event: (aware(event.occurred_at), event.bitrix_event_id))
    warnings = []
    current = _stage_group(deal.stage_title)
    if not events:
        warnings.append("Нет загруженной истории стадий")
    if first and (first > now or (created and first.date() < created.astimezone(MOSCOW).date())):
        warnings.append("Дата начала использования противоречит дате создания или находится в будущем")
        first = None
    reached = first is not None or any(_stage_group(e.stage_title) == "commercial" for e in events)
    if reached and not first:
        warnings.append("Не заполнена корректная дата начала коммерческого использования")
    if current == "commercial" and not reached:
        warnings.append("Коммерческая стадия без даты начала и истории запуска")
        reached = True
    if first and events and aware(events[0].occurred_at).astimezone(MOSCOW).date() > first.date():
        warnings.append("История начинается позже даты первого использования")
    if first and any(_stage_group(e.stage_title) == "commercial"
                     and aware(e.occurred_at).astimezone(MOSCOW).date() < first.date() for e in events):
        warnings.append("В истории есть коммерческое использование раньше даты в поле")
    if events and events[-1].stage_id != deal.stage_id:
        warnings.append("Последняя стадия истории не совпадает с карточкой")

    periods = []
    departures = []
    start = first
    # The field gives a calendar date. Same-day initial transitions precede its
    # true instant and must not fabricate a break at midnight.
    transitions = [e for e in events if first is None or aware(e.occurred_at).astimezone(MOSCOW).date() > first.date()]
    if first:
        same_day_commercial = [e for e in events if aware(e.occurred_at).astimezone(MOSCOW).date() == first.date()
                               and _stage_group(e.stage_title) == "commercial"]
        if same_day_commercial:
            initial_event = same_day_commercial[0]
            if any(_stage_group(e.stage_title) == "lost" and aware(e.occurred_at) < aware(initial_event.occurred_at)
                   and aware(e.occurred_at).astimezone(MOSCOW).date() == first.date() for e in events):
                warnings.append("Отказ и запуск в один день: календарной даты поля недостаточно для порядка периодов")
            transitions = [e for e in events if (aware(e.occurred_at), e.bitrix_event_id)
                           > (aware(initial_event.occurred_at), initial_event.bitrix_event_id)]
        else:
            # Preserve explicit same-day losses; do not interpret earlier working
            # stages on the field date as a cessation of commercial use.
            transitions = [e for e in events if aware(e.occurred_at) >= first
                           and (aware(e.occurred_at).astimezone(MOSCOW).date() > first.date()
                                or _stage_group(e.stage_title) in ("commercial", "lost"))]
    for event in transitions:
        when, group = aware(event.occurred_at), _stage_group(event.stage_title)
        if group == "commercial":
            if start is None:
                start = when
        elif start is not None:
            periods.append({"start": start, "end": when, "end_group": group,
                            "reason": event.stage_title})
            if group == "lost":
                departures.append(when)
            else:
                warnings.append("Есть выход из коммерческой группы не в стадию отказа")
            start = None
    if start is not None:
        periods.append({"start": start, "end": None, "end_group": None, "reason": None})
    if current == "lost" and first and not any(p["end_group"] == "lost" for p in periods):
        warnings.append("Не найдена дата отказа после начала использования")
    if first and bool(periods and periods[-1]["end"] is None) != (current == "commercial"):
        warnings.append("История не подтверждает текущее состояние использования")
    reliable = bool(first and events and not warnings)
    usage_days = sum(((p["end"] or now) - p["start"]).total_seconds() / 86400 for p in periods) if reliable else None
    stage_since = None
    previous_stage = None
    loss_since = None
    previous_group = None
    losses_before_launch = []
    for event in events:
        group = _stage_group(event.stage_title)
        if group == "lost" and previous_group != "lost":
            loss_since = aware(event.occurred_at)
            if not reached or first and loss_since < first:
                losses_before_launch.append(loss_since)
        elif group != "lost":
            loss_since = None
        if event.stage_id != previous_stage:
            stage_since = aware(event.occurred_at)
        previous_stage = event.stage_id
        previous_group = group
    if previous_stage != deal.stage_id:
        stage_since = None
        loss_since = None
    return dict(first=first, reached=reached, periods=periods, departures=departures,
                reliable=reliable, usage_days=usage_days, warnings=list(dict.fromkeys(warnings)),
                stage_since=stage_since, loss_at=loss_since if current == "lost" else None,
                losses_before_launch=losses_before_launch)


def effort_phase(when, timeline):
    first = timeline["first"]
    if not timeline["reached"]:
        return "before"
    if first and when < first:
        return "before"
    if not timeline["reliable"]:
        return "unknown"
    for period in timeline["periods"]:
        if period["start"] <= when and (period["end"] is None or when < period["end"]):
            return "commercial"
    return "break"


def metrics(rows):
    result = {"deals_count": len(rows), "companies_count": len({r["company_id"] for r in rows if r["company_id"]}),
              "amount": str(sum((Decimal(r["amount"]) for r in rows), Decimal(0)))}
    for name, predicate in {
        "working": lambda r: r["group"] == "working",
        "commercial": lambda r: r["group"] == "commercial",
        "ever_commercial": lambda r: r["reached"],
        "lost_before": lambda r: r["group"] == "lost" and not r["reached"],
        "lost_after": lambda r: r["group"] == "lost" and r["reached"],
    }.items():
        selected = [r for r in rows if predicate(r)]
        result[name + "_count"] = len(selected)
        result[name + "_amount"] = str(sum((Decimal(r["amount"]) for r in selected), Decimal(0)))
    result["conversion"] = number(100 * result["ever_commercial_count"] / len(rows)) if rows else None
    decisive = result["ever_commercial_count"] + result["lost_before_count"]
    result["resolved_conversion"] = number(100 * result["ever_commercial_count"] / decisive) if decisive else None
    for prefix, values in {
        "launch": [r["launch_days"] for r in rows if r["launch_days"] is not None],
        "lost_usage": [r["usage_days"] for r in rows if r["group"] == "lost" and r["reached"] and r["usage_days"] is not None],
        "active_usage": [r["usage_days"] for r in rows if r["group"] == "commercial" and r["usage_days"] is not None],
    }.items():
        result[prefix + "_mean_days"] = number(mean(values)) if values else None
        result[prefix + "_median_days"] = number(median(values)) if values else None
        result[prefix + "_sample"] = len(values)
    result["average_commercial_amount"] = str(Decimal(result["ever_commercial_amount"]) / result["ever_commercial_count"]) if result["ever_commercial_count"] else None
    result["reconnections"] = sum(r["reconnections"] or 0 for r in rows)
    result["incomplete_history_count"] = sum(bool(r["warnings"]) for r in rows)
    result["hours"] = number(sum(r["seconds"] or 0 for r in rows)/3600) if any(r["seconds"] is not None for r in rows) else None
    lost_before = [r for r in rows if r["group"] == "lost" and not r["reached"] and r["seconds"] is not None]
    result["lost_before_hours"] = number(sum(r["seconds"] for r in lost_before)/3600) if lost_before else None
    result["overdue_tasks"] = sum(r["overdue_tasks"] for r in rows)
    for month in (1, 3, 6):
        eligible = [r for r in rows if r["retention"][str(month)] is not None]
        result[f"retention_{month}_sample"] = len(eligible)
        result[f"retention_{month}"] = number(100 * sum(r["retention"][str(month)] for r in eligible) / len(eligible)) if eligible else None
        result[f"early_loss_{month}_count"] = sum(r["early_loss"][str(month)] is True for r in rows)
    return result


def build_cr_start_analytics(deals, users, history, tasks, elapsed, commercial_field, *, now=None,
                             employee_id=None, module=None):
    now = aware(now or datetime.now(UTC))
    users_by_id = {str(u.id): u for u in users}
    users_by_bitrix = {u.bitrix_id: u for u in users}
    histories = defaultdict(list)
    for event in history:
        histories[event.deal_id].append(event)
    rows = []
    timelines = {}
    selected = {}
    excluded = 0
    for deal in deals:
        if deal.funnel != "cr_start" or (aware(deal.created_time) and aware(deal.created_time) > now):
            continue
        if _stage_group(deal.stage_title) is None:
            excluded += 1
            continue
        owner = str(deal.implementation_responsible_user_id) if deal.implementation_responsible_user_id else "unassigned"
        if employee_id and owner != employee_id or module and module_name(deal) != module:
            continue
        timeline = usage_timeline(deal, histories[deal.id], raw_date(deal, commercial_field), now)
        timelines[deal.bitrix_id] = timeline
        owner_user = users_by_id.get(owner)
        created = aware(deal.created_time)
        first = timeline["first"]
        row = dict(id=str(deal.id), bitrix_id=deal.bitrix_id, title=deal.title,
                   company_id=deal.company_bitrix_id, company=deal.company_name, module=module_name(deal),
                   owner_id=owner, owner_name=owner_user.full_name if owner_user else "Без ответственного за внедрение",
                   stage=deal.stage_title, group=_stage_group(deal.stage_title), amount=str(deal.opportunity or 0),
                   created_at=iso(created), first_commercial_at=iso(first), reached=timeline["reached"],
                   launch_days=number(max(0, (first-created).total_seconds()/86400)) if first and created else None,
                   age_days=number((now-created).total_seconds()/86400) if created else None,
                   stage_days=number((now-timeline["stage_since"]).total_seconds()/86400) if timeline["stage_since"] else None,
                   history_reliable=timeline["reliable"], warnings=timeline["warnings"],
                   history=[dict(at=iso(e.occurred_at), stage=e.stage_title or e.stage_id)
                            for e in sorted(histories[deal.id], key=lambda e: (aware(e.occurred_at), e.bitrix_event_id))
                            if aware(e.occurred_at) <= now and e.category_id in (None, deal.category_id)],
                   periods=[dict(start=iso(p["start"]), end=iso(p["end"]), reason=p["reason"],
                                 days=number(((p["end"] or now)-p["start"]).total_seconds()/86400)
                                      if timeline["reliable"] else None) for p in timeline["periods"]],
                   usage_days=number(timeline["usage_days"]),
                   usage_months=number(timeline["usage_days"] / (365.25/12)) if timeline["usage_days"] is not None else None,
                   current_period_days=number((now-timeline["periods"][-1]["start"]).total_seconds()/86400)
                       if timeline["reliable"] and timeline["periods"] and timeline["periods"][-1]["end"] is None else None,
                   reconnections=max(0, len(timeline["periods"])-1) if timeline["reliable"] else None,
                   loss_at=iso(timeline["loss_at"]),
                   hours=None, seconds=None, effort=[], tasks=[], overdue_tasks=0, retention={}, early_loss={})
        for month in (1, 3, 6):
            boundary = add_months(first, month) if first else None
            row["retention"][str(month)] = (any(p["start"] <= boundary and (p["end"] is None or boundary < p["end"])
                                              for p in timeline["periods"]) if boundary and boundary <= now and timeline["reliable"] else None)
            row["early_loss"][str(month)] = (timeline["departures"][0] < boundary
                                              if boundary and timeline["departures"] and timeline["reliable"] else None)
        rows.append(row)
        selected[deal.bitrix_id] = row

    issues = []
    tasks_by_id = {}
    unavailable_count = 0
    excluded_seconds = 0
    task_seconds = defaultdict(int)
    seen_excluded = set()
    for entry in elapsed:
        if (entry.bitrix_id not in seen_excluded and entry.seconds is not None and entry.seconds >= 0
                and entry.created_time and aware(entry.created_time) <= now):
            seen_excluded.add(entry.bitrix_id)
            task_seconds[entry.task_bitrix_id] += entry.seconds
    for task in tasks:
        ids = task_deal_ids(task)
        if ids is None:
            issues.append(dict(task_id=task.bitrix_id, title=task.title, reason="Некорректный список связей со сделками"))
            continue
        if not set(ids).intersection(selected):
            continue
        if getattr(task, "api_available", None) is False:
            unavailable_count += 1
            seconds = task_seconds[task.bitrix_id]
            excluded_seconds += seconds
            issues.append(dict(task_id=task.bitrix_id, title=task.title, code="task_card_unavailable",
                               excluded_hours=number(seconds/3600),
                               reason=f"Карточка задачи не возвращается API Битрикса. Исключено {number(seconds/3600):g} ч.; кэш и списания сохранены. Это может быть удаление или отсутствие доступа."))
            continue
        if len(ids) != 1:
            issues.append(dict(task_id=task.bitrix_id, title=task.title, reason="Несколько сделок: " + ", ".join(map(str, ids))))
            continue
        row = selected[ids[0]]
        overdue = bool(task.deadline and aware(task.deadline) < now and task.status != 5 and not task.closed_time)
        task_row = dict(task_id=task.bitrix_id, title=task.title, status=task.status,
                        deadline=iso(task.deadline), overdue=overdue, hours=None, entries=[])
        row["tasks"].append(task_row)
        row["overdue_tasks"] += int(overdue)
        tasks_by_id[task.bitrix_id] = (row, task_row)
    labor = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    seen_elapsed = set()
    for entry in elapsed:
        if entry.bitrix_id in seen_elapsed or entry.task_bitrix_id not in tasks_by_id:
            continue
        seen_elapsed.add(entry.bitrix_id)
        when = aware(entry.created_time)
        if not when or when > now or entry.seconds is None or entry.seconds < 0:
            continue
        row, task_row = tasks_by_id[entry.task_bitrix_id]
        author = users_by_bitrix.get(entry.user_bitrix_id)
        author_id = str(author.id) if author else f"bitrix:{entry.user_bitrix_id}"
        phase = effort_phase(when, timelines[row["bitrix_id"]])
        task_row["entries"].append(dict(id=entry.bitrix_id, author_id=author_id,
            author=author.full_name if author else f"Пользователь №{entry.user_bitrix_id}",
            at=iso(when), seconds=entry.seconds, hours=number(entry.seconds/3600), phase=phase))
        labor[author_id][row["module"]][phase] += entry.seconds
    for row in rows:
        efforts = defaultdict(lambda: defaultdict(int))
        seconds = []
        for task in row["tasks"]:
            if task["entries"]:
                task["hours"] = number(sum(e["seconds"] for e in task["entries"])/3600)
            for entry in task["entries"]:
                seconds.append(entry["seconds"])
                efforts[entry["author_id"]][entry["phase"]] += entry["seconds"]
        row["hours"] = number(sum(seconds)/3600) if seconds else None
        row["seconds"] = sum(seconds) if seconds else None
        row["effort"] = [dict(author_id=author_id, author=users_by_id[author_id].full_name if author_id in users_by_id else author_id,
                              hours=number(sum(phases.values())/3600),
                              **{phase: number(phases[phase]/3600) for phase in ("before", "commercial", "break", "unknown")})
                         for author_id, phases in efforts.items()]
    owner_rows = defaultdict(list)
    for row in rows:
        owner_rows[row["owner_id"]].append(row)
    manager_ids = {str(u.id) for u in users if employee_is_in_department(u, "Отдел внедрения")
                   and (not employee_id or str(u.id) == employee_id)}
    managers = []
    for manager_id in manager_ids:
        user = users_by_id.get(manager_id)
        owned = owner_rows[manager_id]
        def work_stats(module_filter=None):
            phases = defaultdict(int)
            has_entries = False
            for mod, values in labor[manager_id].items():
                if module_filter is None or mod == module_filter:
                    has_entries = True
                    for phase, seconds in values.items():
                        phases[phase] += seconds
            # A sample requires both a first launch date and at least one actual
            # pre-launch entry by this author. No hours from other staff are attributed.
            samples = [sum(e["seconds"] for task in r["tasks"] for e in task["entries"]
                           if e["author_id"] == manager_id and e["phase"] == "before")/3600
                       for r in rows if r["reached"] and (module_filter is None or r["module"] == module_filter)
                       and any(e["author_id"] == manager_id and e["phase"] == "before" for t in r["tasks"] for e in t["entries"])]
            lost_entries = [e["seconds"] for r in rows if r["group"] == "lost" and not r["reached"]
                            and (module_filter is None or r["module"] == module_filter)
                            for task in r["tasks"] for e in task["entries"] if e["author_id"] == manager_id]
            return dict(author_hours=number(sum(phases.values())/3600) if has_entries else None,
                        lost_before_author_hours=number(sum(lost_entries)/3600) if lost_entries else None,
                        **{phase+"_hours": number(phases[phase]/3600) if has_entries else None
                           for phase in ("before", "commercial", "break", "unknown")},
                        launch_effort_mean_hours=number(mean(samples)) if samples else None,
                        launch_effort_sample=len(samples))
        managers.append(dict(id=manager_id, name=user.full_name if user else "Без ответственного" if manager_id=="unassigned" else manager_id,
                             active=user.is_active if user else None, **metrics(owned), **work_stats(),
                             modules=[dict(module=mod, **metrics([r for r in owned if r["module"] == mod]), **work_stats(mod)) for mod in MODULES],
                             deal_ids=[r["id"] for r in owned]))
    monthly = defaultdict(lambda: dict(created=0, first_launch=0, lost_before=0, departures=0, reconnections=0))
    cohorts = defaultdict(list)
    reasons = defaultdict(list)
    for row in rows:
        if row["created_at"]:
            month = row["created_at"][:7]
            monthly[month]["created"] += 1
            cohorts[month].append(row)
        if row["first_commercial_at"]:
            monthly[row["first_commercial_at"][:7]]["first_launch"] += 1
        timeline = timelines[row["bitrix_id"]]
        for loss in timeline["losses_before_launch"]:
            monthly[iso(loss)[:7]]["lost_before"] += 1
        if timeline["reliable"]:
            for departure in timeline["departures"]:
                monthly[iso(departure)[:7]]["departures"] += 1
            for period in timeline["periods"][1:]:
                monthly[iso(period["start"])[:7]]["reconnections"] += 1
        if row["group"] == "lost":
            reasons[(row["owner_id"], row["owner_name"], row["module"], row["stage"], row["reached"])].append(row)
    warnings = ["Результаты сделок — по текущему ответственному; часы — по фактическому автору списания.",
                "В списке менеджеров только отдел внедрения: сначала активные, затем неактивные. Общие итоги и детализация сохраняют сделки и часы остальных участников, поэтому сумма строк менеджеров может отличаться от общих итогов.",
                "Суммы — текущие суммы сделок, не выручка и не исторические суммы на дату перехода.",
                "Нет списаний не означает нулевые трудозатраты. Учитываются только загруженные записи времени; полнота загрузки не подтверждена.",
                "Первый запуск — календарная дата поля (Москва). Условный месяц использования = 30,4375 дня; удержание — на календарные годовщины 1/3/6 месяцев.",
                "Удержание — использование именно на контрольную дату, с учётом возвратов; перерывы исключены из суммарного срока."]
    if excluded:
        warnings.append(f"Исключено сделок вне согласованных стадий: {excluded}")
    if unavailable_count:
        warnings.append(f"Исключено часов по недоступным карточкам задач: {number(excluded_seconds/3600):g}; задач: {unavailable_count}. История сохранена; подробности в ошибках качества данных.")
    return dict(as_of=iso(now), managers=sorted(managers, key=lambda r: (not r["active"], r["name"].casefold())), deals=rows,
                totals=metrics(rows), modules=[dict(module=mod, **metrics([r for r in rows if r["module"]==mod])) for mod in MODULES],
                monthly=[dict(month=month, **values) for month, values in sorted(monthly.items())],
                cohorts=[dict(month=month, **metrics(values)) for month, values in sorted(cohorts.items())],
                losses=[dict(owner_id=key[0], owner_name=key[1], module=key[2], reason=key[3], after_commercial=key[4],
                             count=len(values), amount=str(sum((Decimal(r["amount"]) for r in values), Decimal(0))))
                        for key, values in reasons.items()], issues=issues, warnings=warnings,
                excluded_count=excluded,
                task_availability=dict(unavailable_count=unavailable_count, excluded_hours=number(excluded_seconds/3600)))


async def cr_start_analytics(session, business, *, employee_id=None, module=None, now=None):
    deals = (await session.execute(select(Deal).where(Deal.funnel == "cr_start").order_by(Deal.bitrix_id))).scalars().all()
    users = (await session.execute(select(User))).scalars().all()
    history = (await session.execute(select(DealStageHistory).join(Deal).where(Deal.funnel == "cr_start"))).scalars().all()
    # All task bindings are text JSON; parse once locally rather than issuing N+1 queries.
    all_tasks = (await session.execute(select(BitrixTask).options(load_only(
        BitrixTask.bitrix_id, BitrixTask.title, BitrixTask.crm_deal_ids_json,
        BitrixTask.status, BitrixTask.deadline, BitrixTask.closed_time,
        BitrixTask.api_available, BitrixTask.api_checked_at)))).scalars().all()
    ids = {d.bitrix_id for d in deals}
    tasks = [task for task in all_tasks if (links := task_deal_ids(task)) is None or ids.intersection(links)]
    elapsed = []
    for offset in range(0, len(tasks), 2000):
        elapsed.extend((await session.execute(select(BitrixTaskElapsedItem).options(load_only(
            BitrixTaskElapsedItem.bitrix_id, BitrixTaskElapsedItem.task_bitrix_id,
            BitrixTaskElapsedItem.user_bitrix_id, BitrixTaskElapsedItem.created_time,
            BitrixTaskElapsedItem.seconds)).where(
            BitrixTaskElapsedItem.task_bitrix_id.in_([t.bitrix_id for t in tasks[offset:offset+2000]])))).scalars().all())
    return build_cr_start_analytics(deals, users, history, tasks, elapsed,
                                    business.field_cr_start_commercial_use_date, now=now,
                                    employee_id=employee_id, module=module)
