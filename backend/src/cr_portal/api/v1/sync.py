from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import bitrix_client, db_session
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.services.bitrix_sync import sync_deals, sync_users

router = APIRouter()


@router.post("/users")
async def users_sync(
    session: AsyncSession = Depends(db_session),
    client: BitrixClient = Depends(bitrix_client),
) -> dict[str, int]:
    count = await sync_users(
        session,
        client,
    )

    return {
        "users": count,
    }


@router.post("/deals")
async def deals_sync(
    session: AsyncSession = Depends(db_session),
    client: BitrixClient = Depends(bitrix_client),
) -> dict[str, int]:
    count = await sync_deals(
        session,
        client,
    )

    return {
        "deals": count,
    }


@router.post("/all")
async def all_sync(
    session: AsyncSession = Depends(db_session),
    client: BitrixClient = Depends(bitrix_client),
) -> dict[str, int]:
    users = await sync_users(
        session,
        client,
    )

    deals = await sync_deals(
        session,
        client,
    )

    return {
        "users": users,
        "deals": deals,
    }