import json
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, bitrix_client, db_session
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.deal import Deal
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.deal_analytics import deal_groups_report, deals_in_work_report

router = APIRouter()


class AutoMatchRequest(BaseModel):
    support_ids: list[UUID]


def _source_deal_value(bitrix_id: int | None) -> list[str]:
    """The configured Bitrix CRM field is multiple and stores deals as D_<id>."""
    return [f"D_{bitrix_id}"] if bitrix_id is not None else []


async def _save_source_link(client: BitrixClient, child: Deal, field_code: str, parent_bitrix_id: int | None) -> None:
    try:
        await client.call(
            "crm.item.update",
            {
                "entityTypeId": 2,
                "id": child.bitrix_id,
                "fields": {field_code: _source_deal_value(parent_bitrix_id)},
            },
        )
    except (httpx.HTTPError, RuntimeError) as error:
        raise HTTPException(422, f"Bitrix не принял связь сделки: {error}") from error


@router.get("/deal-groups")
async def deal_groups(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    business = await get_business_settings(session)
    return await deal_groups_report(session, business.field_billing_start_date, business.field_source_deal_id)


@router.get("/deals-in-work")
async def deals_in_work(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    return await deals_in_work_report(session)


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
    await _save_source_link(client, child, business.field_source_deal_id, parent_bitrix_id)
    child.source_deal_bitrix_id = parent_bitrix_id
    raw = json.loads(child.raw_json or "{}")
    raw[business.field_source_deal_id] = _source_deal_value(parent_bitrix_id)
    child.raw_json = json.dumps(raw, ensure_ascii=False)
    await session.commit()
    return {"ok": True}


async def _auto_match_candidates(session: AsyncSession) -> list[dict]:
    business = await get_business_settings(session)
    report = await deal_groups_report(session, business.field_billing_start_date, business.field_source_deal_id)
    return [
        {
            "child": issue["child_deals"][0],
            "parent": issue["auto_candidate"],
            "relation": "Сопровождение → Внедрение" if issue["type"] == "support_without_implementation" else "Внедрение → Техинтеграция",
        }
        for issue in report["issues"]
        if issue["type"] in {"support_without_implementation", "implementation_without_tech"} and issue.get("auto_candidate")
    ]


@router.get("/support-links/auto-match-preview")
async def auto_match_preview(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    return {"items": await _auto_match_candidates(session)}


@router.post("/support-links/auto-match")
async def auto_match_support_links(data: AutoMatchRequest, session: AsyncSession = Depends(db_session), client: BitrixClient = Depends(bitrix_client), _admin=Depends(admin_user)):
    business = await get_business_settings(session)
    if not business.field_source_deal_id:
        raise HTTPException(422, "Не задано поле ссылки на исходную сделку")
    candidates = {item["child"]["id"]: item for item in await _auto_match_candidates(session)}
    updated = 0
    for support_id in data.support_ids:
        item = candidates.get(str(support_id))
        if item is None:
            continue
        child = await session.get(Deal, support_id)
        parent_id = item["parent"]["bitrix_id"]
        if child is None:
            continue
        await _save_source_link(client, child, business.field_source_deal_id, parent_id)
        child.source_deal_bitrix_id = parent_id
        raw = json.loads(child.raw_json or "{}")
        raw[business.field_source_deal_id] = _source_deal_value(parent_id)
        child.raw_json = json.dumps(raw, ensure_ascii=False)
        updated += 1
    await session.commit()
    return {"updated": updated}
