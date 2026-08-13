from fastapi import APIRouter

from cr_portal.schemas.common import EmptyListResponse

router = APIRouter()


@router.get("/", response_model=EmptyListResponse, summary="List users")
async def list_users() -> EmptyListResponse:
    return EmptyListResponse(items=[])
