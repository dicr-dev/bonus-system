from fastapi import APIRouter

from cr_portal.schemas.common import EmptyListResponse

router = APIRouter()


@router.get("/", response_model=EmptyListResponse, summary="List deals")
async def list_deals() -> EmptyListResponse:
    return EmptyListResponse(items=[])
