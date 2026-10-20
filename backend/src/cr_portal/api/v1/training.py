from datetime import date
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import func, or_, select

from cr_portal.api.deps import admin_user, db_session
from cr_portal.models.deal import Deal
from cr_portal.models.training import TrainingReview, TrainingRubric, TrainingSession
from cr_portal.models.user import User
from cr_portal.schemas.training import ReviewInput, RubricInput, TrainingInput
from cr_portal.services import training as service
from cr_portal.services.employee_scope import employee_is_in_department

router = APIRouter(dependencies=[Depends(admin_user)])


def review_dict(item):
    return {key: getattr(item, key) for key in (
        "id", "training_id", "rubric_id", "assessment", "total", "status",
        "created_at", "confirmed_at", "created_by", "confirmed_by",
    )}


def rubric_dict(item):
    return {"id": item.id, "title": item.title, "criteria": item.criteria,
            "created_at": item.created_at}


async def training_or_404(session, training_id, *, text=False):
    try:
        return await service.get_training(session, training_id, text=text)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/options")
async def options(session=Depends(db_session)):
    await service.ensure_default_rubric(session)
    users = (await session.scalars(select(User).order_by(User.is_active.desc(), User.full_name))).all()
    rubrics = (await session.scalars(select(TrainingRubric).order_by(
        TrainingRubric.created_at.desc(), TrainingRubric.id,
    ))).all()
    return {
        "trainers": [{"id": u.id, "full_name": u.full_name, "is_active": u.is_active}
                     for u in users if employee_is_in_department(u, "Отдел внедрения")],
        "rubrics": [rubric_dict(r) for r in rubrics],
        "max_file_bytes": service.MAX_DOCX_BYTES,
    }


@router.post("/rubrics", status_code=201)
async def add_rubric(data: RubricInput, session=Depends(db_session), admin=Depends(admin_user)):
    item = TrainingRubric(title=data.title, criteria=[c.model_dump() for c in data.criteria],
                          created_by=admin.id)
    session.add(item)
    await session.commit()
    return rubric_dict(item)


@router.get("/deals")
async def search_deals(q: str = Query("", max_length=200), session=Depends(db_session)):
    query = select(Deal.id, Deal.bitrix_id, Deal.title, Deal.module_name).order_by(Deal.bitrix_id.desc())
    if q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(or_(Deal.title.ilike(f"%{term}%", escape="\\"),
                                Deal.bitrix_id == (int(q) if q.isascii() and q.isdigit() and len(q) < 10 else -1)))
    return [dict(row._mapping) for row in (await session.execute(query.limit(50))).all()]


@router.get("/sessions")
async def sessions(
    deal_id: UUID | None = None, trainer_id: UUID | None = None,
    date_from: date | None = None, date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    session=Depends(db_session),
):
    filters = session_filters(deal_id, trainer_id, date_from, date_to)
    count = await session.scalar(select(func.count()).select_from(TrainingSession).where(*filters))
    rows = (await session.execute(select(TrainingSession, Deal).join(
        Deal, Deal.id == TrainingSession.deal_id,
    ).where(*filters).order_by(TrainingSession.training_date.desc(), TrainingSession.created_at.desc())
        .limit(limit).offset(offset))).all()
    return {"items": [service.training_dict(item, deal) for item, deal in rows], "total": count}


def session_filters(deal_id, trainer_id, date_from, date_to):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Дата начала позже даты окончания")
    return [condition for condition in (
        TrainingSession.deal_id == deal_id if deal_id else None,
        TrainingSession.trainer_id == trainer_id if trainer_id else None,
        TrainingSession.training_date >= date_from if date_from else None,
        TrainingSession.training_date <= date_to if date_to else None,
    ) if condition is not None]


@router.post("/inspect")
async def inspect_file(file: Annotated[UploadFile, File()]):
    content = await file.read(service.MAX_DOCX_BYTES + 1)
    try:
        _, info = service.extract_docx(content, file.filename or "")
        return info
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/sessions", status_code=201)
async def upload(
    metadata: Annotated[str, Form(max_length=4000)], file: Annotated[UploadFile, File()],
    session=Depends(db_session), admin=Depends(admin_user),
):
    try:
        data = TrainingInput.model_validate_json(metadata)
    except ValidationError as error:
        raise HTTPException(422, "Проверьте сделку, сотрудника, дату, модуль и обозначение участника") from error
    content = await file.read(service.MAX_DOCX_BYTES + 1)
    try:
        return await service.create_training(session, data, content, file.filename or "", admin.id)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/rating")
async def rating(
    rubric_id: UUID, date_from: date | None = None, date_to: date | None = None,
    session=Depends(db_session),
):
    rubric = await session.get(TrainingRubric, rubric_id)
    if rubric is None:
        raise HTTPException(404, "Версия критериев не найдена")
    items = (await session.scalars(select(TrainingSession).where(
        *session_filters(None, None, date_from, date_to),
    ))).all()
    # Join avoids a potentially huge IN list and never loads file/transcript columns.
    reviews = (await session.scalars(select(TrainingReview).join(
        TrainingSession, TrainingSession.id == TrainingReview.training_id,
    ).where(TrainingReview.rubric_id == rubric_id, TrainingReview.status == "confirmed",
            *session_filters(None, None, date_from, date_to)))).all()
    return {"rubric": rubric_dict(rubric), "items": service.build_rating(items, reviews, rubric_id)}


@router.get("/sessions/{training_id}")
async def details(training_id: UUID, session=Depends(db_session)):
    item = await training_or_404(session, training_id, text=True)
    deal = await session.get(Deal, item.deal_id)
    reviews = (await session.scalars(select(TrainingReview).where(
        TrainingReview.training_id == training_id,
    ).order_by(TrainingReview.created_at.desc(), TrainingReview.id))).all()
    return service.training_dict(item, deal) | {
        "transcript": item.transcript, "reviews": [review_dict(r) for r in reviews],
    }


@router.get("/sessions/{training_id}/file")
async def download(training_id: UUID, session=Depends(db_session)):
    item = await training_or_404(session, training_id)
    content = await session.scalar(select(TrainingSession.file_content).where(
        TrainingSession.id == training_id,
    ))
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(item.filename, safe='')}",
                             "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/sessions/{training_id}/prompt")
async def prompt(training_id: UUID, rubric_id: UUID, session=Depends(db_session)):
    item = await training_or_404(session, training_id, text=True)
    rubric = await session.get(TrainingRubric, rubric_id)
    if rubric is None:
        raise HTTPException(404, "Версия критериев не найдена")
    return Response(service.assessment_prompt(item, rubric, item.transcript), media_type="text/plain",
                    headers={"Content-Disposition": 'attachment; filename="training-assessment.txt"',
                             "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/sessions/{training_id}/reviews", status_code=201)
async def add_review(training_id: UUID, data: ReviewInput, session=Depends(db_session), admin=Depends(admin_user)):
    try:
        return review_dict(await service.save_review(session, training_id, data, admin.id))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@router.post("/sessions/{training_id}/reviews/{review_id}/confirm")
async def confirm(training_id: UUID, review_id: UUID, session=Depends(db_session), admin=Depends(admin_user)):
    try:
        return review_dict(await service.confirm_review(session, training_id, review_id, admin.id))
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
