"""Conversion of initiated CR Start and technical integration deals."""
from collections import defaultdict
from sqlalchemy import select
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.services.bonus import raw_date
from cr_portal.services.cr_start_analytics import MOSCOW, aware
from cr_portal.services.deal_analytics import matching_source_ids
from cr_portal.services.implementation_metrics import logistics_details, report_module


def build_conversion_report(deals, users, business):
    names={u.id:u.full_name for u in users}
    tech={d.bitrix_id:d for d in deals if d.funnel=='tech_integration'}
    implementations=[d for d in deals if d.funnel=='implementation']
    children=defaultdict(list)
    parents={}
    for impl in implementations:
        parents[impl.bitrix_id]=matching_source_ids(impl,business.field_source_deal_id,tech)
        for source in parents[impl.bitrix_id]:
            children[source].append(impl)
    result=[]
    for d in deals:
        if d.funnel=='cr_start':
            if d.status=='won':
                continue
            linked=[]
            finished=raw_date(d,business.field_cr_start_commercial_use_date)
            status='retained' if finished else 'lost' if d.status=='lost' else 'pending'
            anchor=d
        elif d.funnel=='tech_integration':
            linked=children[d.bitrix_id]
            anchor=linked[0] if len(linked)==1 else d
            status=('lost' if not linked else 'unknown' if len(linked)>1 else
                    {'won':'retained','lost':'lost','in_progress':'pending'}.get(linked[0].status,'unknown'))
        else:
            continue
        owner=anchor.implementation_responsible_user_id
        if owner is None:
            continue
        start=aware(d.created_time).astimezone(MOSCOW).date() if d.created_time else None
        reason=''
        if not start:
            reason='Не указана дата создания сделки'
            status='unknown'
        elif len(linked)>1:
            reason='Несколько связанных сделок Внедрения'
        elif len(linked)==1 and len(parents[linked[0].bitrix_id])>1:
            reason='Несколько связанных сделок Техинтеграции'
            status='unknown'
            linked=[*linked,*(tech[i] for i in parents[linked[0].bitrix_id] if i!=d.bitrix_id)]
        elif d.funnel=='tech_integration' and not linked:
            reason='Нет связанной сделки Внедрения'
        elif d.funnel=='tech_integration' and linked and linked[0].status=='won' and not linked[0].closed_time:
            reason='Не указана дата завершения Внедрения'
            status='unknown'
        elif d.funnel=='cr_start' and finished and start and finished<start:
            reason='Дата коммерческого использования раньше даты создания'
            status='unknown'
        module=report_module(d if d.funnel=='cr_start' else anchor)
        if not module:
            reason=reason or 'Неизвестный или не заполненный модуль'
            status='unknown'
        kind,warning=logistics_details(anchor,business)
        result.append(dict(id=str(d.id),bitrix_id=d.bitrix_id,title=d.title,company=d.company_name,
            funnel=d.funnel,module=module or 'Не указан',employee_id=str(owner),employee=names.get(owner,'Без имени'),
            opportunity=str(anchor.opportunity or 0),monthly_amount=str(anchor.monthly_amount or 0),machines_count=anchor.machines_count or 0,
            logistics_type=kind,logistics_warning=warning,implementation_employee='',start=start.isoformat() if start else None,
            control_end=None,result=status,reason=reason,
            links=[{'bitrix_id':x.bitrix_id,'title':x.title} for x in [d,*linked]]))
    return result


async def implementation_conversion(session,business):
    deals=list((await session.execute(select(Deal).where(Deal.funnel.in_(['cr_start','tech_integration','implementation'])))).scalars())
    users=list((await session.execute(select(User))).scalars())
    ids=set(business.implementation_metrics_employee_ids or [])
    dates=business.implementation_metrics_hire_dates or {}
    return {'employees':[{'id':str(u.id),'name':u.full_name,'hire_date':dates.get(str(u.id))} for u in users if str(u.id) in ids],
            'deals':[row for row in build_conversion_report(deals,users,business) if row['employee_id'] in ids]}
