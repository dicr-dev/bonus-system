"""Enqueue only history, task cards and report fields after an interrupted full sync."""
import asyncio
import argparse
import json
from datetime import UTC, datetime
from uuid import uuid4

from redis.asyncio import Redis

from cr_portal.core.config import settings
from cr_portal.services.sync_jobs import list_sync_jobs


async def main(*, tasks_only=False, retry_of=None, resume_tasks=False):
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        active = [job for job in await list_sync_jobs(redis) if job["status"] in {"queued", "running"}]
        if active:
            raise RuntimeError("A synchronization is already active; retry after it finishes")
        checkpoint = None
        if resume_tasks:
            if not tasks_only or not retry_of:
                raise ValueError("Resume requires --tasks-only and --retry-of")
            previous = json.loads(await redis.get(f"cr_portal:sync:job:{retry_of}") or "null")
            if not previous or previous.get("status") != "failed" or previous.get("current_funnel") != "tasks":
                raise ValueError("Only a failed task stage can be resumed")
            checkpoint = previous.get("task_checkpoint") or previous.get("task_resume")
            if checkpoint is None:
                # Legacy jobs did not persist a cursor. Recover only the unambiguous
                # final, unfiltered CRM scan while waiting for its next API page.
                source = "Проверка связи задач со сделками — просмотр всех задач"
                if (previous.get("task_source") != source
                        or previous.get("task_queries_done") != previous.get("task_queries_total", 0) - 1
                        or previous.get("task_request_state") not in {"requesting", "retrying"}
                        or not previous.get("task_query_received")):
                    raise ValueError("No safe checkpoint; refusing to restart from the beginning")
                checkpoint = {"queries": [[{}, source, True]], "query_index": 0,
                              "start": previous["task_query_received"]}
        job_id = str(uuid4())
        job = {"job_id": job_id, "type": "tasks_full" if tasks_only else "reporting_resume", "full": True, "status": "queued",
               "progress": 0, "processed": 0, "current_funnel": "tasks" if tasks_only else "stage_history",
               "created_at": datetime.now(UTC).isoformat(), "started_at": None,
               "finished_at": None, "error": None, "retry_of": retry_of}
        if checkpoint is not None:
            job["task_resume"] = checkpoint
        await redis.set(f"cr_portal:sync:job:{job_id}", json.dumps(job), ex=86400 * 7)
        await redis.lpush("cr_portal:sync:deals:queue", job_id)
        print(json.dumps({"job_id": job_id, "status": "queued", "type": job["type"]}))
    finally:
        await redis.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-only", action="store_true")
    parser.add_argument("--retry-of")
    parser.add_argument("--resume-tasks", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(tasks_only=args.tasks_only, retry_of=args.retry_of, resume_tasks=args.resume_tasks))
