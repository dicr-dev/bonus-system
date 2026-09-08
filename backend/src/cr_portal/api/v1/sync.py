import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, bitrix_client, db_session
from cr_portal.core.config import settings
from cr_portal.db.redis import get_redis
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.services.bitrix_sync import sync_users

router = APIRouter()

QUEUE_KEY = "cr_portal:sync:deals:queue"
JOB_PREFIX = "cr_portal:sync:job:"
LAST_SUCCESS_KEY = "cr_portal:sync:deals:last_success"
NIGHTLY_LAST_ATTEMPT_KEY = "cr_portal:sync:nightly:last_attempt"
NIGHTLY_LAST_SUCCESS_KEY = "cr_portal:sync:nightly:last_success"
NIGHTLY_LAST_ERROR_KEY = "cr_portal:sync:nightly:last_error"
NIGHTLY_LAST_RESULT_KEY = "cr_portal:sync:nightly:last_result"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@router.post("/users")
async def users_sync(
    session: AsyncSession = Depends(db_session),
    client: BitrixClient = Depends(bitrix_client),
    _admin=Depends(admin_user),
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
    _admin=Depends(admin_user),
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
    _admin=Depends(admin_user),
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
async def deals_sync_status(_admin=Depends(admin_user)) -> dict:
    redis: Redis = get_redis()

    last_success, nightly_attempt, nightly_success, nightly_error, raw_result = await redis.mget(
        LAST_SUCCESS_KEY,
        NIGHTLY_LAST_ATTEMPT_KEY,
        NIGHTLY_LAST_SUCCESS_KEY,
        NIGHTLY_LAST_ERROR_KEY,
        NIGHTLY_LAST_RESULT_KEY,
    )

    try:
        nightly_result = json.loads(raw_result) if raw_result else None
    except json.JSONDecodeError:
        nightly_result = None

    return {
        "last_success": last_success,
        "nightly_last_attempt": nightly_attempt,
        "nightly_last_success": nightly_success,
        "nightly_last_error": nightly_error,
        "nightly_last_result": nightly_result,
        "nightly_hour": settings.NIGHTLY_SYNC_HOUR,
        "nightly_timezone": settings.NIGHTLY_SYNC_TIMEZONE,
        "nightly_task_months": settings.NIGHTLY_TASK_MONTHS,
    }
