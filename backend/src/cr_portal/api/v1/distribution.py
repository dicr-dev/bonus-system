import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, bitrix_client, db_session
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.deal import Deal
from cr_portal.models.distribution import DistributionDecision
from cr_portal.models.user import User
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.distribution import ASSIGNABLE_FUNNELS, distribution_candidates

router = APIRouter()


class AssignmentInput(BaseModel):
    user_id: UUID


async def _deal_and_candidates(deal_id: UUID, session: AsyncSession):
    deal = await session.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404, "Сделка не найдена")
    if deal.funnel not in ASSIGNABLE_FUNNELS:
        raise HTTPException(422, "Помощник не применяется к CR Start и другим воронкам")
    if deal.status != "in_progress":
        raise HTTPException(422, "Можно назначать только активную сделку")
    deals = list((await session.execute(select(Deal))).scalars())
    users = list((await session.execute(select(User))).scalars())
    business = await get_business_settings(session)
    roster_ids = {UUID(value) for value in business.distribution_employee_ids}
    return deal, distribution_candidates(deal, deals, users, roster_ids=roster_ids)


@router.get("/pending")
async def pending(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    deals = list((await session.execute(select(Deal).where(
        Deal.funnel.in_(ASSIGNABLE_FUNNELS), Deal.status == "in_progress",
        Deal.implementation_responsible_user_id.is_(None),
    ).order_by(Deal.created_time.desc()))).scalars())
    all_deals = list((await session.execute(select(Deal))).scalars())
    users = list((await session.execute(select(User))).scalars())
    business = await get_business_settings(session)
    roster_ids = {UUID(value) for value in business.distribution_employee_ids}
    return {"items": [{
        "id": str(deal.id), "bitrix_id": deal.bitrix_id, "title": deal.title,
        "funnel": deal.funnel, "company_name": deal.company_name, "integration_1c": deal.integration_1c,
        "candidates": distribution_candidates(deal, all_deals, users, roster_ids=roster_ids),
    } for deal in deals]}


@router.get("/{deal_id}/propose")
async def propose(deal_id: UUID, session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    deal, candidates = await _deal_and_candidates(deal_id, session)
    return {"deal_id": str(deal.id), "candidates": candidates}


@router.post("/{deal_id}/assign")
async def assign(deal_id: UUID, data: AssignmentInput, session: AsyncSession = Depends(db_session),
                 client: BitrixClient = Depends(bitrix_client), _admin=Depends(admin_user)):
    deal, candidates = await _deal_and_candidates(deal_id, session)
    candidate = next((item for item in candidates if item["user_id"] == str(data.user_id)), None)
    if candidate is None:
        raise HTTPException(422, "Можно назначить только активного сотрудника отдела внедрения")
    business = await get_business_settings(session)
    if not business.field_implementation_responsible_id:
        raise HTTPException(422, "В настройках не задано поле «Ответственный за внедрение»")
    try:
        await client.call("crm.item.update", {"entityTypeId": 2, "id": deal.bitrix_id,
                                                "fields": {business.field_implementation_responsible_id: candidate["bitrix_id"]}})
    except (httpx.HTTPError, RuntimeError) as error:
        raise HTTPException(422, f"Bitrix не принял назначение: {error}") from error
    decision = DistributionDecision(deal_id=deal.id, proposed_user_id=UUID(candidates[0]["user_id"]),
                                    confirmed_user_id=data.user_id, status="confirmed",
                                    reason=candidate["reason"], resolved_at=datetime.now(UTC))
    deal.implementation_responsible_user_id = data.user_id
    raw = json.loads(deal.raw_json or "{}")
    raw[business.field_implementation_responsible_id] = candidate["bitrix_id"]
    deal.raw_json = json.dumps(raw, ensure_ascii=False)
    session.add(decision)
    await session.commit()
    return {"ok": True, "assigned_user_id": str(data.user_id)}
