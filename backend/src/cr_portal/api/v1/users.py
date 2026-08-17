from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import db_session
from cr_portal.repositories.user import UserRepository
from cr_portal.schemas.users import UserResponse

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(session: AsyncSession = Depends(db_session)) -> list[UserResponse]:
    users = await UserRepository(session).list()
    return [UserResponse.model_validate(user) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(db_session),
) -> UserResponse:
    user = await UserRepository(session).get(user_id)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)
