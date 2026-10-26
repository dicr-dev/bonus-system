import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from cr_portal.api.deps import admin_user
from cr_portal.services import fuel_cards

router = APIRouter()
logger = logging.getLogger(__name__)


async def _preview(import_file: UploadFile):
    if not (import_file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Загрузите файл Excel в формате .xlsx.")
    try:
        return fuel_cards.preview(await import_file.read())
    except ValueError as error:
        logger.info("Fuel-card import preview rejected: %s", error)
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/preview")
async def preview(
    import_file: Annotated[UploadFile, File()], _: Annotated[object, Depends(admin_user)],
):
    return await _preview(import_file)


@router.post("/apply")
async def apply(
    import_file: Annotated[UploadFile, File()], token: Annotated[str, Form(min_length=1, max_length=4096)],
    selected_keys: Annotated[str, Form(max_length=200_000)], confirmed: Annotated[bool, Form()],
    _: Annotated[object, Depends(admin_user)],
):
    if not confirmed:
        raise HTTPException(status_code=422, detail="Подтвердите применение привязок.")
    data = await _preview(import_file)
    try:
        selected = json.loads(selected_keys)
        if not isinstance(selected, list) or not all(isinstance(key, str) for key in selected):
            raise ValueError("Некорректный список выбранных карт.")
        bindings = fuel_cards.selected_bindings(data["items"], set(selected))
        return await fuel_cards.apply(bindings, token)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="Некорректный список выбранных карт.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
