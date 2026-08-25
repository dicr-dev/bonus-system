import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import bitrix_client, db_session
from cr_portal.db.redis import get_redis
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.services.bitrix_sync import sync_users


router = APIRouter()

QUEUE_KEY = "cr_portal:sync:deals:queue"
JOB_PREFIX = "cr_portal:sync:job:"
LAST_SUCCESS_KEY = "cr_portal:sync:deals:last_success"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
    full: bool = Query(default=False),
) -> dict:
    redis: Redis = get_redis()

    job_id = str(uuid4())

    job = {
        "job_id": job_id,
        "type": "deals",
        "full": full,
        "status": "queued",
        "progress": 0,
        "processed": 0,
        "current_funnel": None,
        "created_at": utc_now(),
        "started_at": None,
        "finished_at": None,
        "error": None,
    }

    await redis.set(
        f"{JOB_PREFIX}{job_id}",
        json.dumps(
            job,
            ensure_ascii=False,
        ),
        ex=86400 * 7,
    )

    await redis.lpush(
        QUEUE_KEY,
        job_id,
    )

    return job


@router.get("/jobs/{job_id}")
async def sync_job(
    job_id: str,
) -> dict:
    redis: Redis = get_redis()

    raw = await redis.get(
        f"{JOB_PREFIX}{job_id}"
    )

    if not raw:
        raise HTTPException(
            status_code=404,
            detail="Sync job not found",
        )

    return json.loads(raw)


@router.get("/deals/status")
async def deals_sync_status() -> dict:
    redis: Redis = get_redis()

    last_success = await redis.get(
        LAST_SUCCESS_KEY
    )

    return {
        "last_success": last_success,
    }