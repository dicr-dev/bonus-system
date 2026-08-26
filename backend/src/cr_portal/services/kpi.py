import json
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.models.deal import Deal
from cr_portal.models.kpi import KPIEvent, MonthlyPlan
from cr_portal.models.user import User

def month_start(v:date|datetime)->date:
    if isinstance(v,datetime): v=v.date()
    return date(v.year,v.month,1)
def next_month(v:date)->date:
    return date(v.year+1,1,1) if v.month==12 else date(v.year,v.month+1,1)

async def ensure_kpi_event(session:AsyncSession,deal:Deal)->None:
    if deal.status!="won" or deal.funnel not in {"implementation","cr_start"} or deal.closed_time is None: return
    t="implementation_won" if deal.funnel=="implementation" else "cr_start_won"
    m=month_start(deal.closed_time)
    key=f"{t}:{deal.bitrix_id}:{m.isoformat()}"
    r=await session.execute(select(KPIEvent.id).where(KPIEvent.event_key==key))
    if r.scalar_one_or_none() is not None:return
    session.add(KPIEvent(
      event_key=key,month=m,event_date=deal.closed_time,event_type=t,
      employee_id=deal.implementation_responsible_user_id,deal_id=deal.id,value=Decimal("1"),
      details_json=json.dumps({"bitrix_id":deal.bitrix_id,"funnel":deal.funnel},ensure_ascii=False)
    ))

async def rebuild_missing_events(session:AsyncSession,month:date)->None:
    s=month_start(month); e=next_month(s)
    r=await session.execute(select(Deal).where(
      Deal.status=="won",Deal.funnel.in_(["implementation","cr_start"]),
      Deal.closed_time>=datetime(s.year,s.month,1,tzinfo=timezone.utc),
      Deal.closed_time<datetime(e.year,e.month,1,tzinfo=timezone.utc)
    ))
    for d in r.scalars().all(): await ensure_kpi_event(session,d)
    await session.flush()

async def kpi_summary(session:AsyncSession,month:date)->dict:
    s=month_start(month); await rebuild_missing_events(session,s)
    pr=await session.execute(select(MonthlyPlan).where(MonthlyPlan.month==s))
    p=pr.scalar_one_or_none(); plan=p.plan_value if p else Decimal("0")
    rr=await session.execute(select(KPIEvent,Deal,User).join(Deal,KPIEvent.deal_id==Deal.id).outerjoin(User,KPIEvent.employee_id==User.id).where(KPIEvent.month==s).order_by(KPIEvent.event_date))
    impl=cr=0; emp={}; result=[]
    for ev,d,u in rr.all():
        if ev.event_type=="implementation_won": impl+=1
        else: cr+=1
        k=ev.employee_id
        x=emp.setdefault(k,{"employee_id":k,"employee_name":u.full_name if u else "Без ответственного","implementation":0,"cr_start":0,"fact":0})
        if ev.event_type=="implementation_won": x["implementation"]+=1
        else:x["cr_start"]+=1
        x["fact"]+=1
        result.append({"deal_id":d.id,"bitrix_id":d.bitrix_id,"title":d.title,"funnel":d.funnel,"employee_name":u.full_name if u else None,"monthly_amount":d.monthly_amount,"machines_count":d.machines_count})
    pr=await session.execute(select(Deal,User).outerjoin(User,Deal.implementation_responsible_user_id==User.id).where(Deal.status=="in_progress",Deal.funnel.in_(["implementation","cr_start"])))
    potential=[{"deal_id":d.id,"bitrix_id":d.bitrix_id,"title":d.title,"funnel":d.funnel,"employee_name":u.full_name if u else None,"monthly_amount":d.monthly_amount,"machines_count":d.machines_count} for d,u in pr.all()]
    fact=Decimal(impl+cr); rem=max(Decimal("0"),plan-fact); percent=Decimal("0") if plan==0 else fact/plan*100
    return {"month":s,"plan":plan,"fact":fact,"implementation_fact":impl,"cr_start_fact":cr,"remaining":rem,"completion_percent":percent.quantize(Decimal("0.01")),"potential":len(potential),"forecast":fact+len(potential),"employees":sorted(emp.values(),key=lambda x:-x["fact"]),"result_deals":result,"potential_deals":potential}
