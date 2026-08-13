from redis.asyncio import Redis

from cr_portal.core.config import settings

redis_client: Redis | None = None


async def init_redis() -> None:
    global redis_client
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis is not initialized")
    return redis_client


async def close_redis() -> None:
    if redis_client is not None:
        await redis_client.aclose()
