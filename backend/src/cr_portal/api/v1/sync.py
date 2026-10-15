import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, bitrix_client, db_session
from cr_portal.core.config import settings
from cr_portal.db.redis import get_redis
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.services.bitrix_sync import sync_users
from cr_portal.services.sync_jobs import list_sync_jobs, with_job_activity
from cr_portal.models.oauth import BitrixSyncConnection

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


@router.get("/connection")
async def connection_status(_admin=Depends(admin_user), session=Depends(db_session)):
    connection = (await session.execute(select(BitrixSyncConnection).order_by(
        BitrixSyncConnection.created_at.desc()).limit(1))).scalar_one_or_none()
    return {"configured": connection is not None,
            "admin_bitrix_user_id": connection.admin_bitrix_user_id if connection else None,
            "verified_at": connection.verified_at if connection else None}


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


@router.post("/all")
async def all_sync(_admin=Depends(admin_user)) -> dict:
    redis: Redis = get_redis()
    job_id = str(uuid4())
    job = {"job_id": job_id, "type": "all", "full": True, "status": "queued", "progress": 0, "processed": 0, "current_funnel": "users", "created_at": utc_now(), "started_at": None, "finished_at": None, "error": None}
    await redis.set(f"{JOB_PREFIX}{job_id}", json.dumps(job, ensure_ascii=False), ex=86400 * 7)
    await redis.lpush(QUEUE_KEY, job_id)
    return job


@router.post("/tasks/full")
async def full_tasks_sync(_admin=Depends(admin_user)) -> dict:
    redis: Redis = get_redis()
    job_id = str(uuid4())
    job = {
        "job_id": job_id, "type": "tasks_full", "full": True, "status": "queued",
        "progress": 0, "processed": 0, "current_funnel": None,
        "created_at": utc_now(), "started_at": None, "finished_at": None, "error": None,
    }
    await redis.set(f"{JOB_PREFIX}{job_id}", json.dumps(job, ensure_ascii=False), ex=86400 * 7)
    await redis.lpush(QUEUE_KEY, job_id)
    return job


@router.post("/tasks/recent")
async def recent_tasks_sync(_admin=Depends(admin_user)) -> dict:
    redis: Redis = get_redis()
    job_id = str(uuid4())
    job = {
        "job_id": job_id, "type": "tasks_recent", "full": False, "status": "queued",
        "progress": 0, "processed": 0, "current_funnel": None,
        "created_at": utc_now(), "started_at": None, "finished_at": None, "error": None,
    }
    await redis.set(f"{JOB_PREFIX}{job_id}", json.dumps(job, ensure_ascii=False), ex=86400 * 7)
    await redis.lpush(QUEUE_KEY, job_id)
    return job


@router.get("/jobs")
async def sync_jobs(_admin=Depends(admin_user)) -> list[dict]:
    redis = get_redis()
    return await with_job_activity(redis, await list_sync_jobs(redis))


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

    return (await with_job_activity(redis, [json.loads(raw)]))[0]


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
