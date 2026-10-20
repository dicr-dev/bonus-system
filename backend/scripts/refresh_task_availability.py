"""Check named cached tasks via the administrator API; retain history, no Bitrix writes."""
import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select

from cr_portal.db.session import async_session_factory
from cr_portal.integrations.bitrix.sync_connection import create_sync_client
from cr_portal.models.task import BitrixTask
from cr_portal.services.task_kpi import tasks_by_id
from cr_portal.services.task_sync import REPORTING_TASK_FIELDS, _apply_task_sync_result


async def main(task_ids, *, apply=False):
    async with async_session_factory() as session:
        client = await create_sync_client(session)
        started = datetime.now(UTC)
        unavailable = set()
        cards = await tasks_by_id(client, [str(i) for i in task_ids], REPORTING_TASK_FIELDS,
                                  unavailable_ids=unavailable)
        tasks = (await session.execute(select(BitrixTask).where(BitrixTask.bitrix_id.in_(task_ids)))).scalars().all()
        for task in tasks:
            key = str(task.bitrix_id)
            available = key in cards
            if not available and key not in unavailable:
                print(json.dumps({"task_id": task.bitrix_id, "check": "inconclusive", "changed": False}))
                continue
            _apply_task_sync_result(task, cards.get(key, {}), started, available=available,
                                   confirmed_unavailable=key in unavailable)
            print(json.dumps({"task_id": task.bitrix_id, "api_available": task.api_available, "applied": apply}))
        if apply:
            await session.commit()
        else:
            await session.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", type=int, action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.task_id, apply=args.apply))
