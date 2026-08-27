import json
from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import db_session
from cr_portal.models.bonus import BonusRule
from cr_portal.schemas.app_settings import AppSettingsPayload
from cr_portal.schemas.bonus import RuleCreate, RuleVersionResponse
from cr_portal.services.app_settings import get_app_settings_dict, save_app_settings

router = APIRouter()


@router.get("/app", response_model=AppSettingsPayload)
async def get_app_settings(session: AsyncSession = Depends(db_session)):
    data = await get_app_settings_dict(session)
    await session.commit()
    return AppSettingsPayload(**data)


@router.put("/app", response_model=AppSettingsPayload)
async def update_app_settings(
    data: AppSettingsPayload,
    session: AsyncSession = Depends(db_session),
):
    saved = await save_app_settings(session, data.model_dump())
    return AppSettingsPayload(**asdict(saved))


@router.get("/rules", response_model=list[RuleVersionResponse])
async def list_rules(session: AsyncSession = Depends(db_session)):
    result = await session.execute(
        select(BonusRule).order_by(BonusRule.version.desc())
    )
    return list(result.scalars().all())


@router.post("/rules", response_model=RuleVersionResponse)
async def create_rule(
    data: RuleCreate,
    session: AsyncSession = Depends(db_session),
):
    next_version = int(
        (await session.execute(select(func.max(BonusRule.version)))).scalar_one_or_none()
        or 0
    ) + 1

    previous = (
        await session.execute(
            select(BonusRule)
            .where(BonusRule.effective_to.is_(None))
            .order_by(BonusRule.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if previous and previous.effective_from < data.effective_from:
        previous.effective_to = date.fromordinal(data.effective_from.toordinal() - 1)

    row = BonusRule(
        version=next_version,
        effective_from=data.effective_from,
        config_json=json.dumps(data.config.model_dump(mode="json"), ensure_ascii=False),
        comment=data.comment,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
