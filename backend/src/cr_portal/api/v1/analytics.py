import json
from datetime import date
from io import BytesIO
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, bitrix_client, current_user, db_session
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.deal import Deal
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.deal_analytics import deal_groups_report, deals_in_work_report, gift_info_report, support_analysis_report, weekly_ov_report
from cr_portal.services.employee_scope import employee_is_in_department

router = APIRouter()


class AutoMatchRequest(BaseModel):
    support_ids: list[UUID]


async def business_partners_user(user=Depends(current_user)):
    if not user.is_admin and not employee_is_in_department(user, "Отдел сопровождения"):
        raise HTTPException(status_code=403, detail="Business partners access required")
    return user


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


def _weekly_ov_dates(date_from: date, date_to: date) -> tuple[date, date]:
    if date_from > date_to:
        raise HTTPException(422, "Дата начала не может быть позже даты окончания")
    return date_from, date_to


@router.get("/weekly-ov")
async def weekly_ov(
    date_from: date = Query(...), date_to: date = Query(...),
    session: AsyncSession = Depends(db_session), _admin=Depends(admin_user),
):
    date_from, date_to = _weekly_ov_dates(date_from, date_to)
    return await weekly_ov_report(session, date_from, date_to)


@router.get("/weekly-ov/export")
async def export_weekly_ov(
    date_from: date = Query(...), date_to: date = Query(...),
    session: AsyncSession = Depends(db_session), _admin=Depends(admin_user),
):
    date_from, date_to = _weekly_ov_dates(date_from, date_to)
    rows = await weekly_ov_report(session, date_from, date_to)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Еженедельный отчет ОВ"
    sheet.append([
        "Воронка", "Новые, текущие, передали", "Модуль", "Сотрудник", "Название сделки",
        "Ответственный продавец", "Сумма", "Кол-во ТС", "Статус в воронке",
        "Кол-во дней в текущем статусе", "Кол-во дней в воронке", "Текущий статус по сделке",
    ])
    for row in rows:
        sheet.append([
            "Тех.интеграция" if row["funnel"] == "tech_integration" else "Внедрение",
            row["movement_status"], row["module_name"], row["implementation_responsible_name"], row["title"],
            row["salesperson_name"], float(row["opportunity"]), row["machines_count"], row["stage_title"],
            row["days_in_current_status"], row["days_in_funnel"], row["deal_current_status"],
        ])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(48, max(14, max(len(str(cell.value or "")) for cell in column) + 2))
    sheet.freeze_panes = "A2"
    payload = BytesIO()
    workbook.save(payload)
    payload.seek(0)
    return StreamingResponse(
        payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="weekly_ov_{date_from:%Y-%m-%d}_{date_to:%Y-%m-%d}.xlsx"'},
    )


@router.get("/support-analysis")
async def support_analysis(session: AsyncSession = Depends(db_session), _user=Depends(business_partners_user)):
    return await support_analysis_report(session)


@router.get("/gift-info")
async def gift_info(session: AsyncSession = Depends(db_session), client: BitrixClient = Depends(bitrix_client), _user=Depends(business_partners_user)):
    return await gift_info_report(session, client)


@router.get("/gift-info/export")
async def export_gift_info(session: AsyncSession = Depends(db_session), client: BitrixClient = Depends(bitrix_client), _user=Depends(business_partners_user)):
    rows = await gift_info_report(session, client)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Информация для подарков"
    sheet.append([
        "Название сделки", "Модуль", "ЛПР", "Компания", "Ответственный",
        "Количество машин", "Местонахождение клиента (насел. пункт)",
        "Контактное лицо для курьера",
    ])
    for row in rows:
        sheet.append([
            row["title"], row["module_name"], row["decision_maker"], row["company_name"], row["responsible_name"],
            row["machines_count"], row["location"], row["courier_contact"],
        ])
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(
            60, max(14, max(len(str(cell.value or "")) for cell in column) + 2)
        )
    payload = BytesIO()
    workbook.save(payload)
    payload.seek(0)
    return StreamingResponse(
        payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="gift_info.xlsx"'},
    )


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
