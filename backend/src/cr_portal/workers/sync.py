import asyncio
import json
import logging
from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import select

from cr_portal.core.config import settings
from cr_portal.db.session import async_session_factory
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.oauth import BitrixInstallation
from cr_portal.services.bitrix_sync import sync_deals, sync_users
from cr_portal.services.bonus import calculate_month
from cr_portal.services.task_sync import sync_tasks

logger = logging.getLogger(__name__)

QUEUE_KEY = "cr_portal:sync:deals:queue"
JOB_PREFIX = "cr_portal:sync:job:"
LAST_SUCCESS_KEY = "cr_portal:sync:deals:last_success"
NIGHTLY_LAST_ATTEMPT_KEY = "cr_portal:sync:nightly:last_attempt"
NIGHTLY_LAST_SUCCESS_KEY = "cr_portal:sync:nightly:last_success"
NIGHTLY_LAST_ERROR_KEY = "cr_portal:sync:nightly:last_error"
NIGHTLY_LAST_RESULT_KEY = "cr_portal:sync:nightly:last_result"
NIGHTLY_LOCK_KEY = "cr_portal:sync:nightly:lock"
DAILY_CALCULATION_LAST_ATTEMPT_KEY = "cr_portal:calculations:daily:last_attempt"
DAILY_CALCULATION_LAST_SUCCESS_KEY = "cr_portal:calculations:daily:last_success"
DAILY_CALCULATION_LAST_ERROR_KEY = "cr_portal:calculations:daily:last_error"
DAILY_CALCULATION_LAST_RESULT_KEY = "cr_portal:calculations:daily:last_result"
DAILY_CALCULATION_LOCK_KEY = "cr_portal:calculations:daily:lock"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def nightly_sync_due(
    now: datetime,
    *,
    last_success: str | None,
    last_attempt: str | None,
    hour: int,
    timezone_name: str,
) -> bool:
    local_now = now.astimezone(ZoneInfo(timezone_name))
    if local_now.hour < hour:
        return False

    success = parse_timestamp(last_success)
    if success and success.astimezone(ZoneInfo(timezone_name)).date() == local_now.date():
        return False

    attempt = parse_timestamp(last_attempt)
    return attempt is None or (now.astimezone(UTC) - attempt).total_seconds() >= 3600


async def process_nightly_sync(redis: Redis) -> bool:
    lock_token = str(uuid4())
    acquired = await redis.set(NIGHTLY_LOCK_KEY, lock_token, nx=True, ex=4 * 3600)
    if not acquired:
        return False

    attempt_at = utc_now()
    await redis.set(NIGHTLY_LAST_ATTEMPT_KEY, attempt_at)
    await redis.delete(NIGHTLY_LAST_ERROR_KEY)

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(BitrixInstallation)
                .order_by(BitrixInstallation.created_at.desc())
                .limit(1)
            )
            installation = result.scalar_one_or_none()
            if installation is None:
                raise RuntimeError("Bitrix24 installation not found")

            client = BitrixClient(
                access_token=installation.access_token,
                client_endpoint=installation.client_endpoint,
                session=session,
                installation=installation,
            )
            users_count = await sync_users(session, client)
            deals_count = await sync_deals(
                session,
                client,
                updated_after=await redis.get(LAST_SUCCESS_KEY),
            )
            deal_finished_at = utc_now()
            await redis.set(LAST_SUCCESS_KEY, deal_finished_at)
            task_result = await sync_tasks(
                session,
                client,
                months=settings.NIGHTLY_TASK_MONTHS,
                timezone_name=settings.NIGHTLY_SYNC_TIMEZONE,
            )

        finished_at = utc_now()
        nightly_result = {
            "users": users_count,
            "deals": deals_count,
            **task_result,
            "finished_at": finished_at,
        }
        await redis.set(NIGHTLY_LAST_RESULT_KEY, json.dumps(nightly_result, ensure_ascii=False))
        await redis.set(NIGHTLY_LAST_SUCCESS_KEY, finished_at)
        await redis.delete(NIGHTLY_LAST_ERROR_KEY)
        logger.info("Nightly synchronization completed: %s", nightly_result)
        return True
    except Exception as exc:
        logger.exception("Nightly synchronization failed")
        await redis.set(NIGHTLY_LAST_ERROR_KEY, str(exc))
        return False
    finally:
        if await redis.get(NIGHTLY_LOCK_KEY) == lock_token:
            await redis.delete(NIGHTLY_LOCK_KEY)


async def run_nightly_if_due(redis: Redis) -> None:
    now = datetime.now(UTC)
    if nightly_sync_due(
        now,
        last_success=await redis.get(NIGHTLY_LAST_SUCCESS_KEY),
        last_attempt=await redis.get(NIGHTLY_LAST_ATTEMPT_KEY),
        hour=settings.NIGHTLY_SYNC_HOUR,
        timezone_name=settings.NIGHTLY_SYNC_TIMEZONE,
    ):
        await process_nightly_sync(redis)


def daily_calculation_due(
    now: datetime,
    *,
    last_success: str | None,
    last_attempt: str | None,
    hour: int,
    timezone_name: str,
) -> bool:
    return nightly_sync_due(
        now,
        last_success=last_success,
        last_attempt=last_attempt,
        hour=hour,
        timezone_name=timezone_name,
    )


async def process_daily_calculation(redis: Redis) -> bool:
    """Calculate the current Moscow month once per day after the nightly sync."""
    lock_token = str(uuid4())
    acquired = await redis.set(DAILY_CALCULATION_LOCK_KEY, lock_token, nx=True, ex=4 * 3600)
    if not acquired:
        return False

    attempt_at = utc_now()
    await redis.set(DAILY_CALCULATION_LAST_ATTEMPT_KEY, attempt_at)
    await redis.delete(DAILY_CALCULATION_LAST_ERROR_KEY)

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(BitrixInstallation)
                .order_by(BitrixInstallation.created_at.desc())
                .limit(1)
            )
            installation = result.scalar_one_or_none()
            if installation is None:
                raise RuntimeError("Bitrix24 installation not found")

            client = BitrixClient(
                access_token=installation.access_token,
                client_endpoint=installation.client_endpoint,
                session=session,
                installation=installation,
            )
            local_now = datetime.now(ZoneInfo(settings.NIGHTLY_SYNC_TIMEZONE))
            month = date(local_now.year, local_now.month, 1)
            calculations = await calculate_month(session, month, client=client)

        finished_at = utc_now()
        daily_result = {
            "month": month.isoformat(),
            "calculations": len(calculations),
            "finished_at": finished_at,
        }
        await redis.set(
            DAILY_CALCULATION_LAST_RESULT_KEY,
            json.dumps(daily_result, ensure_ascii=False),
        )
        await redis.set(DAILY_CALCULATION_LAST_SUCCESS_KEY, finished_at)
        await redis.delete(DAILY_CALCULATION_LAST_ERROR_KEY)
        logger.info("Daily calculation completed: %s", daily_result)
        return True
    except Exception as exc:
        logger.exception("Daily calculation failed")
        await redis.set(DAILY_CALCULATION_LAST_ERROR_KEY, str(exc))
        return False
    finally:
        if await redis.get(DAILY_CALCULATION_LOCK_KEY) == lock_token:
            await redis.delete(DAILY_CALCULATION_LOCK_KEY)


async def run_daily_calculation_if_due(redis: Redis) -> None:
    now = datetime.now(UTC)
    if daily_calculation_due(
        now,
        last_success=await redis.get(DAILY_CALCULATION_LAST_SUCCESS_KEY),
        last_attempt=await redis.get(DAILY_CALCULATION_LAST_ATTEMPT_KEY),
        hour=settings.DAILY_CALCULATION_HOUR,
        timezone_name=settings.NIGHTLY_SYNC_TIMEZONE,
    ):
        await process_daily_calculation(redis)


async def update_job(
    redis: Redis,
    job_id: str,
    **values,
) -> None:
    key = f"{JOB_PREFIX}{job_id}"

    current = await redis.get(key)

    if current:
        data = json.loads(current)
    else:
        data = {"job_id": job_id}

    data.update(values)

    await redis.set(
        key,
        json.dumps(
            data,
            ensure_ascii=False,
            default=str,
        ),
        ex=86400 * 7,
    )


async def process_job(
    redis: Redis,
    job_id: str,
) -> None:
    job_key = f"{JOB_PREFIX}{job_id}"

    raw = await redis.get(job_key)

    if not raw:
        logger.warning(
            "Sync job %s not found",
            job_id,
        )
        return

    job = json.loads(raw)

    full = bool(job.get("full", False))

    await update_job(
        redis,
        job_id,
        status="running",
        started_at=utc_now(),
        processed=0,
        progress=0,
        error=None,
    )

    last_success = None

    if not full:
        last_success = await redis.get(
            LAST_SUCCESS_KEY
        )

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(BitrixInstallation)
                .order_by(
                    BitrixInstallation.created_at.desc()
                )
                .limit(1)
            )

            installation = result.scalar_one_or_none()

            if installation is None:
                raise RuntimeError(
                    "Bitrix24 installation not found"
                )

            client = BitrixClient(
                access_token=installation.access_token,
                client_endpoint=installation.client_endpoint,
                session=session,
                installation=installation,
            )

            async def progress_callback(
                funnel: str,
                processed: int,
                progress: int,
            ) -> None:
                await update_job(
                    redis,
                    job_id,
                    current_funnel=funnel,
                    processed=processed,
                    progress=progress,
                )

            count = await sync_deals(
                session,
                client,
                updated_after=last_success,
                progress_callback=progress_callback,
            )

        finished_at = utc_now()

        await redis.set(
            LAST_SUCCESS_KEY,
            finished_at,
        )

        await update_job(
            redis,
            job_id,
            status="completed",
            processed=count,
            progress=100,
            current_funnel=None,
            finished_at=finished_at,
        )

        logger.info(
            "Deal sync %s completed: %s deals",
            job_id,
            count,
        )

    except Exception as exc:
        logger.exception(
            "Deal sync %s failed",
            job_id,
        )

        await update_job(
            redis,
            job_id,
            status="failed",
            error=str(exc),
            finished_at=utc_now(),
        )


async def worker() -> None:
    redis = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    logger.info(
        "Synchronization worker started; nightly sync at %02d:00 and daily calculation at %02d:00 %s",
        settings.NIGHTLY_SYNC_HOUR,
        settings.DAILY_CALCULATION_HOUR,
        settings.NIGHTLY_SYNC_TIMEZONE,
    )

    try:
        while True:
            await run_nightly_if_due(redis)
            await run_daily_calculation_if_due(redis)

            result = await redis.brpop(
                QUEUE_KEY,
                timeout=5,
            )

            if result is None:
                continue

            _, job_id = result

            await process_job(
                redis,
                job_id,
            )

    finally:
        await redis.aclose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    asyncio.run(worker())


if __name__ == "__main__":
    main()
