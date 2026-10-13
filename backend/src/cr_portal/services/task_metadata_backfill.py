import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select

from cr_portal.db.redis import get_redis
from cr_portal.models.task import BitrixTask
from cr_portal.services.task_kpi import tasks_by_id
from cr_portal.services.task_sync import _apply_task_snapshot


async def enqueue_task_metadata_backfill() -> str:
    redis = get_redis()
    job_id = str(uuid4())
    job = {"job_id": job_id, "type": "task_metadata", "full": True,
           "status": "queued", "progress": 0, "processed": 0,
           "current_funnel": "task_metadata", "created_at": datetime.now(UTC).isoformat(),
           "started_at": None, "finished_at": None, "error": None}
    await redis.set(f"cr_portal:sync:job:{job_id}", json.dumps(job), ex=86400 * 7)
    await redis.set("cr_portal:sync:task_metadata:last_job", job_id)
    await redis.lpush("cr_portal:sync:deals:queue", job_id)
    return job_id


async def backfill_task_metadata(session, client, progress_callback=None) -> dict:
    """Restore missing historical cards without recalculating bonus snapshots."""
    tasks = list((await session.execute(select(BitrixTask).where(or_(
        BitrixTask.title == "Название задачи недоступно в Bitrix",
        BitrixTask.raw_json.contains('"metadata_source": "user_confirmed"'),
    )).order_by(BitrixTask.bitrix_id))).scalars())
    fields_payload = await client.call("tasks.task.getFields")
    fields = fields_payload.get("result", {}).get("fields", {})
    extra_select = list(fields) if isinstance(fields, dict) else []
    restored = 0
    unavailable = []
    for offset in range(0, len(tasks), 50):
        batch = tasks[offset:offset + 50]
        payloads = await tasks_by_id(client, [str(task.bitrix_id) for task in batch], extra_select=extra_select)
        for task in batch:
            payload = payloads.get(str(task.bitrix_id))
            if payload:
                _apply_task_snapshot(task, payload, datetime.now(UTC))
                restored += 1
            else:
                unavailable.append(task.bitrix_id)
        await session.commit()
        if progress_callback:
            await progress_callback("task_metadata", offset + len(batch), int((offset + len(batch)) * 100 / len(tasks)))
    return {"total": len(tasks), "restored": restored, "unavailable": len(unavailable), "unavailable_ids": unavailable}
