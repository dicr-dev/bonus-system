import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, current_user, db_session
from cr_portal.models.reporting import ReportField, SavedReport
from cr_portal.models.user import User
from cr_portal.services.employee_scope import employee_is_in_department
from cr_portal.services.report_builder import refresh_report_fields, run_report

router = APIRouter()

def _report(item: SavedReport) -> dict:
    return {"id": str(item.id), "title": item.title, "source": item.source, "visibility": item.visibility, "config": json.loads(item.config_json), "author_id": str(item.author_id), "updated_at": item.updated_at}

def _viewer(user: User) -> None:
    if not user.is_admin and not employee_is_in_department(user, "Отдел внедрения"):
        raise HTTPException(403, "Report access is limited to implementation department")

@router.post("/fields/refresh")
async def fields_refresh(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    return {"created": await refresh_report_fields(session)}

@router.get("/fields")
async def fields(source: str | None = None, session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    query = select(ReportField).order_by(ReportField.entity_type, ReportField.title)
    if source: query = query.where(ReportField.entity_type == source)
    return [{"id": str(x.id), "source": x.entity_type, "code": x.code, "title": x.title, "field_type": x.field_type, "is_enabled": x.is_enabled} for x in (await session.execute(query)).scalars()]

@router.put("/fields/{field_id}")
async def field_update(field_id: UUID, payload: dict, session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    field = await session.get(ReportField, field_id)
    if field is None: raise HTTPException(404, "Field not found")
    field.is_enabled = bool(payload.get("is_enabled"))
    await session.commit()
    return {"id": str(field.id), "is_enabled": field.is_enabled}

@router.get("/reports")
async def reports(session: AsyncSession = Depends(db_session), user: User = Depends(current_user)):
    _viewer(user)
    query = select(SavedReport).order_by(SavedReport.updated_at.desc())
    if not user.is_admin: query = query.where(SavedReport.visibility == "shared")
    return [_report(x) for x in (await session.execute(query)).scalars()]

@router.post("/reports")
async def report_create(payload: dict, session: AsyncSession = Depends(db_session), user: User = Depends(admin_user)):
    source, title = str(payload.get("source", "")), str(payload.get("title", "")).strip()
    if source not in {"deals", "tasks", "stage_history"} or not title: raise HTTPException(422, "Title and source are required")
    visibility = payload.get("visibility", "private")
    if visibility not in {"private", "shared"}: raise HTTPException(422, "Unsupported visibility")
    item = SavedReport(title=title, source=source, visibility=visibility, config_json=json.dumps(payload.get("config", {}), ensure_ascii=False), author_id=user.id)
    session.add(item); await session.commit(); await session.refresh(item)
    return _report(item)

@router.put("/reports/{report_id}")
async def report_update(report_id: UUID, payload: dict, session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    item = await session.get(SavedReport, report_id)
    if item is None: raise HTTPException(404, "Report not found")
    for attr in ("title", "visibility"):
        if attr in payload: setattr(item, attr, payload[attr])
    if "config" in payload: item.config_json = json.dumps(payload["config"], ensure_ascii=False)
    await session.commit(); await session.refresh(item)
    return _report(item)

@router.get("/reports/{report_id}/run")
async def report_run(report_id: UUID, session: AsyncSession = Depends(db_session), user: User = Depends(current_user)):
    _viewer(user)
    item = await session.get(SavedReport, report_id)
    if item is None or (not user.is_admin and item.visibility != "shared"): raise HTTPException(404, "Report not found")
    return await run_report(session, item.source, json.loads(item.config_json))

@router.post("/run")
async def report_preview(payload: dict, session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    try: return await run_report(session, str(payload.get("source")), payload.get("config", {}))
    except ValueError as error: raise HTTPException(422, str(error))
