from fastapi import APIRouter, Depends, HTTPException, Query

from cr_portal.api.deps import admin_user, bitrix_client, db_session
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.monthly_rating import monthly_rating_report, refresh_type_metadata

router = APIRouter(dependencies=[Depends(admin_user)])


@router.get("/monthly-rating")
async def report(month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"), session=Depends(db_session)):
    business = await get_business_settings(session)
    try:
        return await monthly_rating_report(session, business, month)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/monthly-rating/type-metadata")
async def refresh_metadata(session=Depends(db_session), client=Depends(bitrix_client)):
    business = await get_business_settings(session)
    try:
        return await refresh_type_metadata(session, client, business.task_1c_type_field)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        # Never expose HTTP request URLs / tokens from an upstream exception.
        raise HTTPException(502, "Не удалось загрузить справочник типов задач из Битрикса") from error
