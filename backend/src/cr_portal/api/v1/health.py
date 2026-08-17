from fastapi import APIRouter
from sqlalchemy import text

from cr_portal.db.redis import get_redis
from cr_portal.db.session import async_session_factory

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "CR Integration Portal"}


@router.get("/health/db")
async def health_db() -> dict[str, str]:
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "postgresql"}


@router.get("/health/redis")
async def health_redis() -> dict[str, str]:
    await get_redis().ping()
    return {"status": "ok", "redis": "connected"}
