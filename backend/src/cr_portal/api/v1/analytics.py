import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, bitrix_client, db_session
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.deal import Deal
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.deal_analytics import deal_groups_report

router = APIRouter()


@router.get("/deal-groups")
async def deal_groups(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    business = await get_business_settings(session)
    return await deal_groups_report(session, business.field_billing_start_date)


@router.put("/deal-links/{child_id}")
async def save_deal_link(child_id: UUID, parent_bitrix_id: int | None, session: AsyncSession = Depends(db_session), client: BitrixClient = Depends(bitrix_client), _admin=Depends(admin_user)):
    child = await session.get(Deal, child_id)
    if child is None or child.funnel not in {"implementation", "support"}:
        raise HTTPException(422, "Выберите сделку Внедрения или Сопровождения")
    expected = "tech_integration" if child.funnel == "implementation" else "implementation"
    if parent_bitrix_id is not None:
        parent = await session.execute(select(Deal).where(Deal.bitrix_id == parent_bitrix_id, Deal.funnel == expected))
        if parent.scalar_one_or_none() is None:
            raise HTTPException(422, "Выбрана сделка неверной воронки")
    business = await get_business_settings(session)
    if not business.field_source_deal_id:
        raise HTTPException(422, "Не задано поле ссылки на исходную сделку")
    await client.call("crm.item.update", {"entityTypeId": 2, "id": child.bitrix_id, "fields": {business.field_source_deal_id: parent_bitrix_id}})
    child.source_deal_bitrix_id = parent_bitrix_id
    raw = json.loads(child.raw_json or "{}")
    raw[business.field_source_deal_id] = parent_bitrix_id
    child.raw_json = json.dumps(raw, ensure_ascii=False)
    await session.commit()
    return {"ok": True}


@router.post("/support-links/auto-match")
async def auto_match_support_links(session: AsyncSession = Depends(db_session), client: BitrixClient = Depends(bitrix_client), _admin=Depends(admin_user)):
    business = await get_business_settings(session)
    report = await deal_groups_report(session, business.field_billing_start_date)
    updated = 0
    for issue in report["issues"]:
        if issue["type"] != "support_without_implementation" or not issue.get("auto_candidate"):
            continue
        child = await session.get(Deal, UUID(issue["child_deals"][0]["id"]))
        parent_id = issue["auto_candidate"]["bitrix_id"]
        if child is None:
            continue
        await client.call("crm.item.update", {"entityTypeId": 2, "id": child.bitrix_id, "fields": {business.field_source_deal_id: parent_id}})
        child.source_deal_bitrix_id = parent_id
        raw = json.loads(child.raw_json or "{}")
        raw[business.field_source_deal_id] = parent_id
        child.raw_json = json.dumps(raw, ensure_ascii=False)
        updated += 1
    await session.commit()
    return {"updated": updated}
