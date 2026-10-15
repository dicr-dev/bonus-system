from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.db.session import get_db
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.integrations.bitrix.sync_connection import create_sync_client
from cr_portal.repositories.users import UserRepository


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


async def bitrix_client(
    session: AsyncSession = Depends(db_session),
) -> BitrixClient:
    try:
        return await create_sync_client(session)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


async def current_user(
    request: Request,
    session: AsyncSession = Depends(db_session),
):
    bitrix_id = request.session.get("bitrix_user_id")

    if bitrix_id is None:
        raise HTTPException(
            status_code=401,
            detail="Bitrix authorization required",
        )

    user = await UserRepository(session).by_bitrix_id(
        int(bitrix_id)
    )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="User is not synchronized or inactive",
        )

    return user


async def admin_user(
    user=Depends(current_user),
):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user
