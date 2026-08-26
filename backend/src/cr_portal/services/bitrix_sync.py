import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.core.config import settings
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.deal import Deal
from cr_portal.repositories.deals import DealRepository
from cr_portal.repositories.users import UserRepository
from cr_portal.services.kpi import ensure_kpi_event

STATUS_MAP={"process":"in_progress","success":"won","failure":"lost","apology":"lost"}
ProgressCallback=Callable[[str,int,int],Awaitable[None]]

def funnels():
    p=[(settings.BITRIX_TECH_INTEGRATION_CATEGORY_ID,"tech_integration"),
       (settings.BITRIX_IMPLEMENTATION_CATEGORY_ID,"implementation"),
       (settings.BITRIX_CR_START_CATEGORY_ID,"cr_start"),
       (settings.BITRIX_SUPPORT_CATEGORY_ID,"support")]
    return {int(i):n for i,n in p if i is not None}
def _dt(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except Exception:return None
def _dec(v):
    if v in (None,""):return Decimal("0")
    if isinstance(v,str) and "|" in v:v=v.split("|",1)[0]
    try:return Decimal(str(v))
    except Exception:return Decimal("0")
def _int(v):
    if v in (None,""):return 0
    if isinstance(v,list):v=v[0] if v else 0
    try:return int(float(v))
    except Exception:return 0
def _bool(v):
    if isinstance(v,bool):return v
    s=str(v or "").strip()
    if s=="199":return True
    if s=="200":return False
    return s.upper() in {"Y","YES","TRUE","1","ДА"}

async def get_stage_semantics(c,category_id):
    entity="DEAL_STAGE" if category_id==0 else f"DEAL_STAGE_{category_id}"
    x=await c.call("crm.status.list",{"filter":{"ENTITY_ID":entity},"order":{"SORT":"ASC"}})
    out={}
    for s in x.get("result",[]):
        sid=str(s.get("STATUS_ID") or "");sem=str((s.get("EXTRA") or {}).get("SEMANTICS") or "").lower()
        if sid:out[sid]=sem
    return out

async def sync_users(session,c):
    items=await c.call_all("user.get",{});repo=UserRepository(session);n=0
    for i in items:
        raw=i.get("ID") or i.get("id")
        if raw is None:continue
        name=" ".join(str(x) for x in [i.get("NAME") or i.get("name"),i.get("LAST_NAME") or i.get("lastName")] if x).strip() or f"Bitrix user {raw}"
        u=await repo.upsert(int(raw),i.get("EMAIL") or i.get("email"),name,i.get("WORK_POSITION") or i.get("workPosition"))
        av=i.get("ACTIVE") if "ACTIVE" in i else i.get("active")
        u.is_active=av if isinstance(av,bool) else str(av or "").strip().upper() in {"Y","YES","TRUE","1"}
        n+=1
    await session.commit();return n

async def sync_deals(session,c,*,updated_after=None,progress_callback=None):
    drepo=DealRepository(session);urepo=UserRepository(session);total=0;fs=funnels()
    select_fields=["id","title","categoryId","stageId","assignedById","opportunity","createdTime","updatedTime","closedTime"]
    custom=[settings.BITRIX_FIELD_MONTHLY_AMOUNT,settings.BITRIX_FIELD_MACHINES_COUNT,
      settings.BITRIX_FIELD_INTEGRATION_1C,settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID,
      settings.BITRIX_FIELD_SOURCE_DEAL_ID,settings.BITRIX_FIELD_SALES_BONUS_USER_ID,
      settings.BITRIX_FIELD_CLIENT_WORKS,*settings.cr_start_boolean_fields]
    for f in custom:
        if f and f not in select_fields:select_fields.append(f)
    for idx,(cat,funnel) in enumerate(fs.items()):
        sems=await get_stage_semantics(c,cat);flt={"categoryId":cat}
        if updated_after:flt[">=updatedTime"]=updated_after
        items=await c.call_all("crm.item.list",{"entityTypeId":2,"select":select_fields,"filter":flt})
        for i in items:
            raw=i.get("id")
            if raw is None:continue
            bid=int(raw);d=await drepo.by_bitrix_id(bid)
            if d is None:d=Deal(bitrix_id=bid,category_id=cat,funnel=funnel,stage_id="",status="in_progress",title="");session.add(d)
            stage=str(i.get("stageId") or "");d.status=STATUS_MAP.get(sems.get(stage,""),"in_progress")
            d.category_id=cat;d.funnel=funnel;d.stage_id=stage;d.title=str(i.get("title") or "");d.opportunity=_dec(i.get("opportunity"))
            aid=_int(i.get("assignedById"));d.bitrix_assigned_by_id=aid or None
            au=await urepo.by_bitrix_id(aid) if aid else None;d.responsible_user_id=au.id if au else None
            if settings.BITRIX_FIELD_MONTHLY_AMOUNT:d.monthly_amount=_dec(i.get(settings.BITRIX_FIELD_MONTHLY_AMOUNT))
            if settings.BITRIX_FIELD_MACHINES_COUNT:d.machines_count=_int(i.get(settings.BITRIX_FIELD_MACHINES_COUNT))
            if settings.BITRIX_FIELD_INTEGRATION_1C:d.integration_1c=_bool(i.get(settings.BITRIX_FIELD_INTEGRATION_1C))
            d.implementation_responsible_user_id=None
            if settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID:
                x=_int(i.get(settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID));u=await urepo.by_bitrix_id(x) if x else None
                d.implementation_responsible_user_id=u.id if u else None
            d.sales_bonus_user_id=None
            if settings.BITRIX_FIELD_SALES_BONUS_USER_ID:
                x=_int(i.get(settings.BITRIX_FIELD_SALES_BONUS_USER_ID));u=await urepo.by_bitrix_id(x) if x else None
                d.sales_bonus_user_id=u.id if u else None
            if settings.BITRIX_FIELD_SOURCE_DEAL_ID:d.source_deal_bitrix_id=_int(i.get(settings.BITRIX_FIELD_SOURCE_DEAL_ID)) or None
            d.created_time=_dt(i.get("createdTime"));d.updated_time=_dt(i.get("updatedTime"));d.closed_time=_dt(i.get("closedTime"))
            d.raw_json=json.dumps(i,ensure_ascii=False,default=str)
            await session.flush();await ensure_kpi_event(session,d);total+=1
        await session.commit()
        if progress_callback:await progress_callback(funnel,total,int((idx+1)/len(fs)*100))
    return total
