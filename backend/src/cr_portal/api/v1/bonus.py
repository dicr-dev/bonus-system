from fastapi import APIRouter

from cr_portal.schemas.common import EmptyListResponse

router = APIRouter()


@router.get("/", response_model=EmptyListResponse, summary="List bonus reports")
async def list_bonus() -> EmptyListResponse:
    return EmptyListResponse(items=[])
