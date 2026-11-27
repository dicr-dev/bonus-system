"""Cohort retention for the implementation department, based on local CRM data."""
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select

from cr_portal.models.deal import Deal
from cr_portal.models.reporting import DealStageHistory
from cr_portal.models.user import User
from cr_portal.services.bonus import raw_date, raw_value
from cr_portal.services.cr_start_analytics import MOSCOW, add_months, aware, usage_timeline
from cr_portal.services.deal_analytics import company_id, matching_source_ids

MODULES = ("CR Start", "CR Start ТМ", "CR Start Эксплуатация", "Логистика",
           "Эксплуатация", "Топливный модуль", "Загрузки", "Топливный планировщик",
           "Дальнобой + ТМ", "Маршрутизация", "Каргоран Лайт + ТМ")


def report_module(deal):
    name = " ".join((deal.module_name or "").split()).casefold()
    if deal.funnel == "cr_start":
        return {"": "CR Start", "кр старт": "CR Start", "cr start": "CR Start", "логистика": "CR Start",
                "кр старт тм": "CR Start ТМ", "cr start тм": "CR Start ТМ",
                "кр старт эксплуатация": "CR Start Эксплуатация",
                "cr start эксплуатация": "CR Start Эксплуатация"}.get(name)
    aliases = {"кр старт": "Логистика", "cr start": "Логистика",
               "кр старт эксплуатация": "Эксплуатация", "cr start эксплуатация": "Эксплуатация"}
    return aliases.get(name) or {name.casefold(): name for name in MODULES[3:]}.get(name)


def logistics_details(deal, business):
    if report_module(deal) != "Логистика":
        return None, ""
    integration = raw_value(deal, getattr(business, "field_integration_1c", ""))
    machines = raw_value(deal, getattr(business, "field_machines_count", ""))
    if isinstance(integration, list):
        integration = integration[0] if len(integration) == 1 else None
    if isinstance(machines, list):
        machines = machines[0] if len(machines) == 1 else None
    flag = str(integration).strip().casefold() if integration is not None else ""
    yes = ("y", "yes", "1", "true", "да", "199")
    no = ("n", "no", "0", "false", "нет", "200")
    if flag not in (*yes, *no):
        return None, "Не заполнено или не распознано поле интеграции 1С"
    try:
        if machines is None or str(machines).strip() == "":
            raise ValueError
        count = int(str(machines).strip())
        if count < 0:
            raise ValueError
    except (ValueError, TypeError):
        return ("Логистика без интеграции" if flag in no else None), "Не заполнено или некорректно количество ТС"
    if flag in no:
        return "Логистика без интеграции", ""
    return ("Логистика с интеграцией" if count > 1 else "Логистика только интеграция"), ""


def build_report(deals, users, history, business, now=None):
    now = aware(now or datetime.now(UTC)).astimezone(MOSCOW)
    deals = [d for d in deals if not (d.funnel in ("cr_start", "support") and d.status == "won")]
    users = {u.id: u.full_name for u in users}
    events = defaultdict(list)
    for event in history:
        events[event.deal_id].append(event)
    implementations = {d.bitrix_id: d for d in deals if d.funnel == "implementation"}
    supports = defaultdict(list)
    for d in deals:
        if d.funnel == "support" and company_id(d) and report_module(d):
            supports[(company_id(d), report_module(d))].append(d)
    chains, continuation, errors = {}, set(), set()
    for group in supports.values():
        group.sort(key=lambda d: (aware(d.created_time) or datetime.max.replace(tzinfo=UTC), d.bitrix_id))
        for index, deal in enumerate(group):
            if index:
                previous = group[index - 1]
                if not previous.created_time or not deal.created_time or previous.status == "in_progress" or not previous.closed_time:
                    errors.update((previous.id, deal.id))
                elif aware(deal.created_time) <= aware(previous.closed_time):
                    errors.update((previous.id, deal.id))
                else:
                    continuation.add(deal.id)
            chains[deal.id] = group

    rows = []
    for deal in deals:
        if (deal.funnel not in ("cr_start", "support") or deal.id in continuation
                or deal.implementation_responsible_user_id is None
                or (deal.funnel == "cr_start" and " ".join((deal.stage_title or "").split()).casefold() == "перешли в логистику")
                or (deal.funnel != "cr_start" and not (deal.module_name or "").strip())):
            continue
        module = report_module(deal)
        start_date = raw_date(deal, business.field_cr_start_commercial_use_date) if deal.funnel == "cr_start" else (aware(deal.created_time).astimezone(MOSCOW).date() if deal.created_time else None)
        if not start_date:
            continue
        start = datetime(start_date.year, start_date.month, 1, tzinfo=MOSCOW)
        end = add_months(start, 4)
        owner = deal.implementation_responsible_user_id
        owner_name = users.get(owner, "Без ответственного за внедрение")
        reason, result = "", "unknown"
        if not module:
            reason = "Неизвестный или не заполненный модуль"
        elif start > now:
            reason = "Дата начала в будущем"
        elif deal.funnel == "cr_start":
            timeline = usage_timeline(deal, events[deal.id], start_date, now, getattr(business, "cr_start_lost_stages", None))
            if not timeline["reliable"]:
                reason = "; ".join(timeline["warnings"]) or "Недостаточно истории стадий"
            elif end > now:
                result = "pending"
            else:
                first = timeline["periods"][0] if timeline["periods"] else None
                result = "retained" if first and (first["end"] is None or first["end"] >= end) else "lost"
        else:
            chain = chains.get(deal.id, [deal])
            if not company_id(deal):
                reason = "Не указана компания"
            elif any(d.id in errors for d in chain):
                reason = "Несколько одновременных сделок или неизвестна дата закрытия"
            elif any(d.status not in ("in_progress", "lost") or (d.status == "lost" and not d.closed_time) for d in chain):
                reason = "Неизвестен статус или дата закрытия"
            elif end > now:
                result = "pending"
            else:
                # A later deal is a continuation only when it starts before the end of the control month.
                candidates = [d for d in chain if d.created_time and aware(d.created_time) < end]
                last = candidates[-1] if candidates else deal
                result = "retained" if last.status == "in_progress" or (last.closed_time and aware(last.closed_time) >= end) else "lost"
        sources = matching_source_ids(deal, business.field_source_deal_id, implementations) if deal.funnel == "support" else []
        logistics_type, logistics_warning = logistics_details(deal, business)
        source_names = sorted({users.get(implementations[i].implementation_responsible_user_id) for i in sources if implementations[i].implementation_responsible_user_id != owner} - {None})
        rows.append(dict(id=str(deal.id), bitrix_id=deal.bitrix_id, title=deal.title, company=deal.company_name, funnel=deal.funnel,
                         opportunity=str(deal.opportunity or 0), monthly_amount=str(deal.monthly_amount or 0), machines_count=deal.machines_count or 0,
                         logistics_type=logistics_type, logistics_warning=logistics_warning,
                         module=module or "Не указан", employee_id=str(owner) if owner else "unassigned", employee=owner_name,
                         implementation_employee=", ".join(source_names), start=start_date.isoformat() if start_date else None,
                         control_end=end.date().isoformat() if end else None, result=result, reason=reason))
    return rows


async def implementation_metrics(session, business):
    deals = list((await session.execute(select(Deal).where(Deal.funnel.in_(("cr_start", "support", "implementation"))))).scalars())
    users = list((await session.execute(select(User))).scalars())
    history = list((await session.execute(select(DealStageHistory).join(Deal).where(Deal.funnel == "cr_start"))).scalars())
    selected_ids = set(business.implementation_metrics_employee_ids or [])
    selected = [u for u in users if str(u.id) in selected_ids]
    rows = [row for row in build_report(deals, users, history, business) if row["employee_id"] in selected_ids]
    dates = getattr(business, "implementation_metrics_hire_dates", None) or {}
    return {"employees": [{"id": str(u.id), "name": u.full_name, "hire_date": dates.get(str(u.id))} for u in selected], "deals": rows}
