import json
from datetime import UTC, datetime

JOB_PREFIX = "cr_portal:sync:job:"
HEARTBEAT_PREFIX = "cr_portal:sync:heartbeat:"


async def with_job_activity(redis, jobs, *, now=None):
    if not jobs:
        return []
    now = now or datetime.now(UTC)
    values = await redis.mget([HEARTBEAT_PREFIX + job["job_id"] for job in jobs])
    result = []
    for job, value in zip(jobs, values):
        timestamp = value.decode() if isinstance(value, bytes) else value
        alive = None
        if job.get("status") == "running" and job.get("heartbeat_supported"):
            try:
                seen = datetime.fromisoformat(timestamp or job["started_at"])
                if seen.tzinfo is None:
                    seen = seen.replace(tzinfo=UTC)
                age = (now - seen).total_seconds()
                alive = age < 60 if timestamp else None if age < 60 else False
            except (TypeError, ValueError, KeyError):
                alive = None
        result.append({**job, "heartbeat_at": timestamp, "worker_alive": alive})
    return result


async def list_sync_jobs(redis, recent_limit=10):
    """Restore all active jobs and recent results from Redis, independent of browser state."""
    jobs = {}
    keys = []

    async def read_batch():
        for raw in await redis.mget(keys):
            try:
                job = json.loads(raw) if raw else None
            except (ValueError, TypeError):
                continue
            if isinstance(job, dict) and job.get("job_id") and job.get("status") in {
                "queued", "running", "completed", "failed",
            }:
                jobs[job["job_id"]] = job

    async for key in redis.scan_iter(match=f"{JOB_PREFIX}*", count=100):
        keys.append(key)
        if len(keys) == 100:
            await read_batch()
            keys.clear()
    if keys:
        await read_batch()
    ordered = sorted(jobs.values(), key=lambda job: job.get("created_at") or "", reverse=True)
    active = [job for job in ordered if job["status"] in {"queued", "running"}]
    recent = [job for job in ordered if job["status"] in {"completed", "failed"}]
    return active + recent[:recent_limit]
