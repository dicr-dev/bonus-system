from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.db.session import get_db
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.oauth import BitrixInstallation
from cr_portal.repositories.users import UserRepository


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


async def bitrix_client(
    session: AsyncSession = Depends(db_session),
) -> BitrixClient:
    result = await session.execute(
        select(BitrixInstallation)
        .order_by(BitrixInstallation.created_at.desc())
        .limit(1)
    )

    installation = result.scalar_one_or_none()

    if installation is None:
        raise HTTPException(
            status_code=503,
            detail="Bitrix24 installation not found",
        )

    return BitrixClient(
        access_token=installation.access_token,
        client_endpoint=installation.client_endpoint,
        session=session,
        installation=installation,
    )


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

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User is not synchronized",
        )

    return user