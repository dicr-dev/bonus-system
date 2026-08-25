import asyncio
import json
import logging
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select

from cr_portal.core.config import settings
from cr_portal.db.session import async_session_factory
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.oauth import BitrixInstallation
from cr_portal.services.bitrix_sync import sync_deals


logger = logging.getLogger(__name__)

QUEUE_KEY = "cr_portal:sync:deals:queue"
JOB_PREFIX = "cr_portal:sync:job:"
LAST_SUCCESS_KEY = "cr_portal:sync:deals:last_success"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
        "Deal synchronization worker started"
    )

    try:
        while True:
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

    asyncio.run(worker())


if __name__ == "__main__":
    main()