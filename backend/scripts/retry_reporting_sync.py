"""Enqueue only history, task cards and report fields after an interrupted full sync."""
import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from redis.asyncio import Redis

from cr_portal.core.config import settings
from cr_portal.services.sync_jobs import list_sync_jobs


async def main():
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        active = [job for job in await list_sync_jobs(redis) if job["status"] in {"queued", "running"}]
        if active:
            raise RuntimeError("A synchronization is already active; retry after it finishes")
        job_id = str(uuid4())
        job = {"job_id": job_id, "type": "reporting_resume", "full": True, "status": "queued",
               "progress": 0, "processed": 0, "current_funnel": "stage_history",
               "created_at": datetime.now(UTC).isoformat(), "started_at": None,
               "finished_at": None, "error": None}
        await redis.set(f"cr_portal:sync:job:{job_id}", json.dumps(job), ex=86400 * 7)
        await redis.lpush("cr_portal:sync:deals:queue", job_id)
        print(json.dumps({"job_id": job_id, "status": "queued", "type": job["type"]}))
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
