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
STATUS_MAP={"process":"in_progress","success":"success","failure":"failed","apology":"failed"}
ProgressCallback=Callable[[str,int,int],Awaitable[None]]

def funnels():
    pairs=[(settings.BITRIX_TECH_INTEGRATION_CATEGORY_ID,"tech_integration"),(settings.BITRIX_IMPLEMENTATION_CATEGORY_ID,"implementation"),(settings.BITRIX_CR_START_CATEGORY_ID,"cr_start"),(settings.BITRIX_SUPPORT_CATEGORY_ID,"support")]
    return {int(x):y for x,y in pairs if x is not None}

def _parse_datetime(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except (TypeError,ValueError):return None

def _decimal(v):
    if v in (None,""):return Decimal("0")
    if isinstance(v,str) and "|" in v:v=v.split("|",1)[0]
    try:return Decimal(str(v))
    except (TypeError,ValueError):return Decimal("0")

def _int(v):
    if v in (None,""):return 0
    if isinstance(v,list):
        if not v:return 0
        v=v[0]
    try:return int(float(v))
    except (TypeError,ValueError):return 0

def _bool(v):
    if isinstance(v,bool):return v
    if v in (None,""):return False
    s=str(v).strip()
    if s=="199":return True
    if s=="200":return False
    return s.upper() in {"Y","YES","TRUE","1","ДА"}

async def get_stage_semantics(client,category_id):
    entity_id="DEAL_STAGE" if category_id==0 else f"DEAL_STAGE_{category_id}"
    response=await client.call("crm.status.list",{"filter":{"ENTITY_ID":entity_id},"order":{"SORT":"ASC"}})
    result={}
    for stage in response.get("result",[]):
        sid=str(stage.get("STATUS_ID") or ""); sem=str((stage.get("EXTRA") or {}).get("SEMANTICS") or "").lower()
        if sid:result[sid]=sem
    return result

async def sync_users(session,client):
    response=await client.call("user.get",{"FILTER":{"ACTIVE":True}}); items=response.get("result",[]); repo=UserRepository(session); synced=0
    for item in items:
        raw_id=item.get("ID") or item.get("id")
        if raw_id is None:continue
        full_name=" ".join(str(v) for v in [item.get("NAME") or item.get("name"),item.get("LAST_NAME") or item.get("lastName")] if v).strip() or f"Bitrix user {raw_id}"
        await repo.upsert(bitrix_id=int(raw_id),email=item.get("EMAIL") or item.get("email"),full_name=full_name,position=item.get("WORK_POSITION") or item.get("workPosition")); synced+=1
    await session.commit(); return synced

async def sync_deals(session,client,*,updated_after=None,progress_callback=None):
    configured=funnels(); deal_repo=DealRepository(session); user_repo=UserRepository(session); total=0
    select_fields=["id","title","categoryId","stageId","assignedById","opportunity","createdTime","updatedTime","closedTime"]
    for f in [settings.BITRIX_FIELD_MONTHLY_AMOUNT,settings.BITRIX_FIELD_MACHINES_COUNT,settings.BITRIX_FIELD_INTEGRATION_1C,settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID]:
        if f and f not in select_fields:select_fields.append(f)
    funnel_items=list(configured.items()); funnel_count=len(funnel_items)
    for funnel_index,(category_id,funnel) in enumerate(funnel_items):
        stage_semantics=await get_stage_semantics(client,category_id); deal_filter={"categoryId":category_id}
        if updated_after:deal_filter[">=updatedTime"]=updated_after
        items=await client.call_all("crm.item.list",{"entityTypeId":2,"select":select_fields,"filter":deal_filter})
        for item in items:
            raw=item.get("id")
            if raw is None:continue
            bitrix_id=int(raw); deal=await deal_repo.by_bitrix_id(bitrix_id)
            if deal is None:
                deal=Deal(bitrix_id=bitrix_id,category_id=category_id,funnel=funnel,stage_id="",status="in_progress",title=""); session.add(deal)
            stage_id=str(item.get("stageId") or ""); deal.status=STATUS_MAP.get(stage_semantics.get(stage_id,""),"in_progress"); deal.category_id=category_id; deal.funnel=funnel; deal.stage_id=stage_id; deal.title=str(item.get("title") or ""); deal.opportunity=_decimal(item.get("opportunity"))
            assigned=_int(item.get("assignedById")); deal.bitrix_assigned_by_id=assigned or None; au=await user_repo.by_bitrix_id(assigned) if assigned else None; deal.responsible_user_id=au.id if au else None
            if settings.BITRIX_FIELD_MONTHLY_AMOUNT:deal.monthly_amount=_decimal(item.get(settings.BITRIX_FIELD_MONTHLY_AMOUNT))
            if settings.BITRIX_FIELD_MACHINES_COUNT:deal.machines_count=_int(item.get(settings.BITRIX_FIELD_MACHINES_COUNT))
            if settings.BITRIX_FIELD_INTEGRATION_1C:deal.integration_1c=_bool(item.get(settings.BITRIX_FIELD_INTEGRATION_1C))
            deal.implementation_responsible_user_id=None
            if settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID:
                impl=_int(item.get(settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID)); iu=await user_repo.by_bitrix_id(impl) if impl else None
                if iu:deal.implementation_responsible_user_id=iu.id
            deal.created_time=_parse_datetime(item.get("createdTime")); deal.closed_time=_parse_datetime(item.get("closedTime")); deal.raw_json=json.dumps(item,ensure_ascii=False,default=str); total+=1
        await session.commit(); progress=int(((funnel_index+1)/funnel_count)*100)
        if progress_callback:await progress_callback(funnel,total,progress)
    return total
