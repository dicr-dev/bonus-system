import json
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.core.config import settings
from cr_portal.models.bonus import BonusCalculation, BonusCalculationItem, ManualBonusEvent
from cr_portal.models.deal import Deal
from cr_portal.models.kpi import CalculationIssue
from cr_portal.models.user import User
from cr_portal.services.rules import current_client_bonus, decimal, get_rules, implementation_rate
from cr_portal.schemas.bonus import BonusInput, BonusResult
from cr_portal.services.rules import DEFAULT_RULES

CENT=Decimal("0.01")
def money(v:Decimal)->Decimal:return v.quantize(CENT,rounding=ROUND_HALF_UP)
def month_start(v:date)->date:return date(v.year,v.month,1)
def add_months(v:date,n:int)->date:
    y=v.year+(v.month-1+n)//12;m=(v.month-1+n)%12+1
    return date(y,m,1)
def dt(v:date)->datetime:return datetime(v.year,v.month,v.day,tzinfo=timezone.utc)
def raw_value(d:Deal,f:str):
    if not f or not d.raw_json:return None
    try:return json.loads(d.raw_json).get(f)
    except Exception:return None
def truthy(v)->bool:
    if isinstance(v,bool):return v
    return str(v).strip().upper() in {"Y","YES","TRUE","1","ДА","199"}

async def add_issue(session,month,severity,code,message,employee_id=None,deal_id=None):
    row=CalculationIssue(month=month,severity=severity,code=code,message=message,employee_id=employee_id,deal_id=deal_id,details_json="{}")
    session.add(row);return row

async def diagnose_month(session:AsyncSession,month:date):
    month=month_start(month)
    r=await session.execute(select(CalculationIssue).where(CalculationIssue.month==month,CalculationIssue.calculation_id.is_(None)))
    for x in r.scalars().all(): await session.delete(x)
    if not settings.BITRIX_FIELD_SOURCE_DEAL_ID:
        await add_issue(session,month,"warning","SOURCE_DEAL_FIELD_NOT_CONFIGURED","Не настроено поле ID сделки-источника.")
    if not settings.BITRIX_FIELD_SALES_BONUS_USER_ID:
        await add_issue(session,month,"warning","SALES_USER_FIELD_NOT_CONFIGURED","Не настроено поле сотрудника, получающего бонус за продажу.")
    if not settings.cr_start_boolean_fields:
        await add_issue(session,month,"warning","CR_START_FIELDS_NOT_CONFIGURED","Не настроены поля «КР Старт: ...».")
    if not settings.BITRIX_TASK_TRAINING_BONUS_FIELD:
        await add_issue(session,month,"warning","TRAINING_TASK_FIELD_NOT_CONFIGURED","Не настроено поле задачи «Бонус за обучение = Да».")
    if not settings.BITRIX_FIELD_CLIENT_WORKS:
        await add_issue(session,month,"warning","CLIENT_WORKS_NOT_CONFIGURED","Не задано техническое определение «клиент работает».")

    rr=await session.execute(select(Deal))
    for d in rr.scalars().all():
        if d.status not in {"in_progress","won","lost"}:
            await add_issue(session,month,"critical","UNKNOWN_STATUS",f"Неизвестный статус {d.status}",deal_id=d.id)
        if d.status=="won" and d.funnel in {"tech_integration","implementation","cr_start"} and d.implementation_responsible_user_id is None:
            await add_issue(session,month,"critical","NO_IMPLEMENTATION_RESPONSIBLE","Нет «Ответственного за внедрение».",deal_id=d.id)
        if d.status=="won" and d.funnel in {"implementation","cr_start"} and Decimal(d.monthly_amount or 0)<=0:
            await add_issue(session,month,"critical","NO_MONTHLY_AMOUNT","Нет суммы оплаты в месяц.",employee_id=d.implementation_responsible_user_id,deal_id=d.id)
        if d.funnel=="support" and d.machines_count<=0:
            await add_issue(session,month,"warning","NO_MACHINES","Нет количества машин.",employee_id=d.implementation_responsible_user_id,deal_id=d.id)
    await session.flush()
    r=await session.execute(select(CalculationIssue).where(CalculationIssue.month==month).order_by(CalculationIssue.severity,CalculationIssue.code))
    return list(r.scalars().all())

async def latest_version(session,employee_id,month):
    r=await session.execute(select(func.max(BonusCalculation.version)).where(BonusCalculation.employee_id==employee_id,BonusCalculation.month==month))
    return int(r.scalar_one_or_none() or 0)+1

async def calculate_month(session:AsyncSession,month:date,initiated_by_id:UUID|None=None):
    month=month_start(month); end=add_months(month,1); period_to=date.fromordinal(end.toordinal()-1)
    rules_version,rules=await get_rules(session,month)
    issues=await diagnose_month(session,month)
    users=(await session.execute(select(User))).scalars().all()
    user_ids={u.id for u in users}
    c=defaultdict(list)

    # Tech integration.
    r=await session.execute(select(Deal).where(
      Deal.funnel=="tech_integration",Deal.status=="won",Deal.closed_time>=dt(month),Deal.closed_time<dt(end)))
    for d in r.scalars().all():
        e=d.implementation_responsible_user_id
        if not e or not d.integration_1c:continue
        base=Decimal(d.opportunity or 0);rate=decimal(rules["tech_integration_rate"])
        c[e].append((d,"tech_integration",base,rate,Decimal("1"),money(base*rate),True,"Тех интеграция: 50% × сумма сделки"))

    # Implementation and CR Start-as-implementation: three months.
    eligible=defaultdict(list)
    start3=add_months(month,-2)
    r=await session.execute(select(Deal).where(
      Deal.funnel.in_(["implementation","cr_start"]),Deal.status=="won",
      Deal.closed_time>=dt(start3),Deal.closed_time<dt(end)))
    for d in r.scalars().all():
        e=d.implementation_responsible_user_id
        if not e or not d.closed_time or Decimal(d.monthly_amount or 0)<=0:continue
        cm=month_start(d.closed_time.date());delta=(month.year-cm.year)*12+month.month-cm.month
        if delta not in {0,1,2}:continue
        if d.funnel=="cr_start":
            fields=settings.cr_start_boolean_fields
            if not fields:continue
            values=[raw_value(d,f) for f in fields]
            if any(truthy(v) for v in values):
                if delta==0:
                    fixed=decimal(rules["cr_start_fixed"])
                    c[e].append((d,"cr_start_fixed",fixed,Decimal("1"),Decimal("1"),fixed,False,"CR Start: фиксированный бонус 10 000 ₽"))
                continue
        eligible[e].append((d,"cr_start_implementation" if d.funnel=="cr_start" else "implementation"))
    for e,rows in eligible.items():
        total=sum((Decimal(d.monthly_amount or 0) for d,_ in rows),Decimal("0"))
        rate=implementation_rate(total,rules)
        for d,t in rows:
            base=Decimal(d.monthly_amount or 0)
            c[e].append((d,t,base,rate,Decimal("1"),money(base*rate),True,f"Внедрение: {rate*100}% × сумма оплаты в месяц"))

    # Sale, if actual field configured and synchronized.
    if settings.BITRIX_FIELD_SALES_BONUS_USER_ID:
        r=await session.execute(select(Deal).where(
          Deal.funnel=="tech_integration",Deal.sales_bonus_user_id.is_not(None),
          Deal.closed_time>=dt(month),Deal.closed_time<dt(end)))
        for d in r.scalars().all():
            e=d.sales_bonus_user_id
            if not e:continue
            base=Decimal(d.opportunity or 0);rate=decimal(rules["sales_rate"])
            c[e].append((d,"sale",base,rate,Decimal("1"),money(base*rate),False,"Продажа: 10% × сумма сделки"))

    # Manual hours/training until TBD task sources are configured.
    r=await session.execute(select(ManualBonusEvent).where(ManualBonusEvent.event_date>=month,ManualBonusEvent.event_date<end))
    for ev in r.scalars().all():
        if ev.event_type=="support_hours":
            rate=decimal(rules["support_hour_rate"]);before=money(Decimal(ev.quantity)*rate)
            c[ev.employee_id].append((None,"support_hours",rate,rate,Decimal(ev.quantity),before,True,f"Сопровождение: {ev.quantity} ч × {rate} ₽",ev))
        elif ev.event_type=="training":
            rate=decimal(rules["training_bonus"]);before=money(Decimal(ev.quantity)*rate)
            c[ev.employee_id].append((None,"training",rate,rate,Decimal(ev.quantity),before,True,f"Обучение: {ev.quantity} × {rate} ₽",ev))

    # Current clients only when both TBD definitions are configured.
    if settings.BITRIX_FIELD_SOURCE_DEAL_ID and settings.BITRIX_FIELD_CLIENT_WORKS:
        r=await session.execute(select(Deal).where(Deal.funnel=="support",Deal.status=="in_progress",Deal.source_deal_bitrix_id.is_not(None)))
        for d in r.scalars().all():
            if not truthy(raw_value(d,settings.BITRIX_FIELD_CLIENT_WORKS)):continue
            sr=await session.execute(select(Deal).where(Deal.bitrix_id==d.source_deal_bitrix_id));src=sr.scalar_one_or_none()
            if not src or src.funnel!="implementation" or src.status!="won" or not src.implementation_responsible_user_id:continue
            before=current_client_bonus(d.machines_count,rules)
            if before>0:
                c[src.implementation_responsible_user_id].append((d,"current_client",Decimal(d.machines_count),before,Decimal("1"),before,True,f"Текущий клиент: {d.machines_count} машин → {before} ₽"))

    divider=decimal(rules["divider"]);out=[]
    for e,rows in c.items():
        if e not in user_ids:continue
        subdiv=sum((x[5] for x in rows if x[6]),Decimal("0"))
        fixed=sum((x[5] for x in rows if x[1]=="cr_start_fixed"),Decimal("0"))
        sales=sum((x[5] for x in rows if x[1]=="sale"),Decimal("0"))
        implbase=sum((x[2] for x in rows if x[1] in {"implementation","cr_start_implementation"}),Decimal("0"))
        techbase=sum((x[2] for x in rows if x[1]=="tech_integration"),Decimal("0"))
        hours=sum((x[4] for x in rows if x[1]=="support_hours"),Decimal("0"))
        training=int(sum((x[4] for x in rows if x[1]=="training"),Decimal("0")))
        calc=BonusCalculation(
          employee_id=e,period_from=month,period_to=period_to,implementation_total=implbase,
          tech_integration_total=techbase,support_hours=hours,sales_total=sales,training_count=training,
          total_bonus=money(subdiv/divider+fixed+sales),details_json="{}",month=month,
          version=await latest_version(session,e,month),status="completed",rules_version=rules_version,
          rules_snapshot_json=json.dumps(rules,ensure_ascii=False),subtotal_dividable=money(subdiv),
          cr_start_fixed_total=money(fixed),issues_count=len(issues),initiated_by_id=initiated_by_id)
        session.add(calc);await session.flush()
        for x in rows:
            d,t,base,rate,qty,before,use_div,desc=x[:8]
            ev=x[8] if len(x)>8 else None
            final=money(before/divider) if use_div else money(before)
            session.add(BonusCalculationItem(
              calculation_id=calc.id,employee_id=e,deal_id=(d.id if d else (ev.deal_id if ev else None)),
              bonus_type=t,source_type=("manual_event" if ev else "deal"),
              source_external_id=(str(ev.id) if ev else (str(d.bitrix_id) if d else None)),
              base_amount=money(base),rate=rate,quantity=qty,amount_before_divider=money(before),
              divider_applied=use_div,amount_final=final,description=desc,
              details_json=json.dumps({"divider":str(divider) if use_div else None},ensure_ascii=False)))
        out.append(calc)
    await session.commit();return out


# Backward-compatible pure aggregate calculator.
# New production calculations use calculate_month() and persist history.
def calculate_bonus(data: BonusInput) -> BonusResult:
    config = DEFAULT_RULES
    implementation_bonus = money(
        data.implementation_total
        * implementation_rate(data.implementation_total, config)
    )
    tech_integration_bonus = money(
        data.tech_integration_total
        * decimal(config["tech_integration_rate"])
    )
    support_bonus = money(
        data.support_hours
        * decimal(config["support_hour_rate"])
    )
    sales_bonus = money(
        data.sales_total
        * decimal(config["sales_rate"])
    )
    training_bonus = money(
        Decimal(data.training_count)
        * decimal(config["training_bonus"])
    )
    cr_start_fixed_bonus = money(data.cr_start_fixed_total)

    dividable = (
        implementation_bonus
        + tech_integration_bonus
        + support_bonus
        + training_bonus
    )
    subtotal = money(
        dividable
        + sales_bonus
        + cr_start_fixed_bonus
    )
    total = money(
        dividable / decimal(config["divider"])
        + sales_bonus
        + cr_start_fixed_bonus
    )

    return BonusResult(
        employee_id=data.employee_id,
        implementation_bonus=implementation_bonus,
        tech_integration_bonus=tech_integration_bonus,
        support_bonus=support_bonus,
        sales_bonus=sales_bonus,
        training_bonus=training_bonus,
        cr_start_fixed_bonus=cr_start_fixed_bonus,
        subtotal=subtotal,
        total=total,
    )
