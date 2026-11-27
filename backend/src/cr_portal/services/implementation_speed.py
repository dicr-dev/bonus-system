"""Launch duration, grouped by the creation date of the source deal."""
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select

from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.services.bonus import raw_date
from cr_portal.services.cr_start_analytics import MOSCOW, aware
from cr_portal.services.deal_analytics import matching_source_ids
from cr_portal.services.implementation_metrics import logistics_details, report_module


def build_speed_report(deals, users, business):
    users = {u.id: u.full_name for u in users}
    tech = {d.bitrix_id: d for d in deals if d.funnel == 'tech_integration'}
    implementations = [d for d in deals if d.funnel == 'implementation']
    children = defaultdict(list)
    sources = {}
    for d in implementations:
        sources[d.bitrix_id] = matching_source_ids(d, business.field_source_deal_id, tech)
        for source in sources[d.bitrix_id]:
            children[source].append(d)
    rows = []
    for d in deals:
        if d.funnel == 'cr_start' and d.status != 'won':
            end = raw_date(d, business.field_cr_start_commercial_use_date)
            if not end:
                continue
            linked = []
            start = aware(d.created_time).astimezone(MOSCOW).date() if d.created_time else None
            error = '' if start else 'Не указана дата создания CR Start'
        elif d.funnel == 'implementation' and d.status == 'won':
            ids = sources[d.bitrix_id]
            linked = [tech[i] for i in ids]
            related = {item.bitrix_id: item for i in ids for item in children[i]}
            end = aware(d.closed_time).astimezone(MOSCOW).date() if d.closed_time else None
            start = aware(linked[0].created_time).astimezone(MOSCOW).date() if len(linked) == 1 and linked[0].created_time else None
            if not ids:
                error = 'Нет связи с Техинтеграцией'
            elif len(ids) > 1:
                error = 'Несколько связанных сделок Техинтеграции'
            elif len(related) > 1:
                error = 'Несколько связанных сделок Внедрения'
            elif not start:
                error = 'Не указана дата создания Техинтеграции'
            elif not end:
                error = 'Не указана дата завершения Внедрения'
            else:
                error = ''
            linked += [item for item in related.values() if item.bitrix_id != d.bitrix_id]
        else:
            continue
        owner = d.implementation_responsible_user_id
        if owner is None:
            continue
        if start and end and end < start:
            error = 'Дата завершения раньше даты начала'
        is_error = bool(error) and not (d.funnel == 'cr_start' and d.bitrix_id == 48941 and error == 'Дата завершения раньше даты начала')
        module = report_module(d)
        if not module:
            error = error or 'Неизвестный или не заполненный модуль'
            is_error = True
        logistics_type, logistics_warning = logistics_details(d, business)
        rows.append({'id': str(d.id), 'bitrix_id': d.bitrix_id, 'title': d.title,
                     'employee_id': str(owner), 'employee': users.get(owner, 'Без имени'),
                     'module': module or 'Не указан', 'funnel': d.funnel,
                     'start': start.isoformat() if start else None, 'end': end.isoformat() if end else None,
                     'days': (end-start).days+1 if start and end and not error else None,
                     'reason': error, 'is_error': is_error, 'logistics_type': logistics_type, 'logistics_warning': logistics_warning,
                     'links': [{'bitrix_id': item.bitrix_id, 'title': item.title} for item in [d, *linked]]})
    return rows


async def implementation_speed(session, business):
    deals = list((await session.execute(select(Deal).where(Deal.funnel.in_(['cr_start','tech_integration','implementation'])))).scalars())
    users = list((await session.execute(select(User))).scalars())
    ids = set(business.implementation_metrics_employee_ids or [])
    dates = business.implementation_metrics_hire_dates or {}
    return {'employees': [{'id': str(u.id), 'name': u.full_name, 'hire_date': dates.get(str(u.id))} for u in users if str(u.id) in ids],
            'deals': [row for row in build_speed_report(deals, users, business) if row['employee_id'] in ids]}
