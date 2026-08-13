from fastapi import APIRouter

from cr_portal.schemas.common import EmptyListResponse

router = APIRouter()


@router.get("/", response_model=EmptyListResponse, summary="List reports")
async def list_reports() -> EmptyListResponse:
    return EmptyListResponse(items=[])
