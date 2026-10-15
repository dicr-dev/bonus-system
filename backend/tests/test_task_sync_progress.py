import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, patch

import httpx

from cr_portal.models.task import BitrixTask
from cr_portal.services.sync_jobs import HEARTBEAT_PREFIX, with_job_activity
from cr_portal.services.task_sync import sync_reporting_tasks
from cr_portal.workers.sync import job_heartbeat


def result(rows):
    return Obj(scalars=lambda: rows)


class PageSession:
    def __init__(self, people=(), deals=()):
        self.people = people
        self.deals = deals
        self.rows = {}
        self.pending = []
        self.commits = 0

    async def execute(self, query):
        table = query.get_final_froms()[0].name
        if table == "users":
            return result(self.people)
        if table == "deals":
            return result(self.deals)
        return result(list(self.rows.values()))

    def add(self, row):
        self.pending.append(row)

    async def commit(self):
        self.rows.update({row.bitrix_id: row for row in self.pending})
        self.pending.clear()
        self.commits += 1


class TaskProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_page_committed_before_next_request_and_duplicate_count_is_unique(self):
        session = PageSession(deals=[100])
        calls = 0

        async def api(method, params):
            nonlocal calls
            self.assertEqual(method, "tasks.task.list")
            if calls == 0:
                calls += 1
                return {"result": {"tasks": [{"id": "1", "title": "First", "ufCrmTask": ["D_100"]}]}, "next": 50, "total": 3}
            self.assertIn(1, session.rows)  # Not just pending, but committed before page two.
            self.assertEqual(params["start"], 50)
            return {"result": {"tasks": [{"id": "1", "title": "Updated", "ufCrmTask": ["D_100"]},
                                           {"id": "2", "title": "Unrelated", "ufCrmTask": ["D_999"]}]}, "total": 3}

        updates = []
        async def progress(values):
            updates.append(values)
        count = await sync_reporting_tasks(session, Obj(call=api), progress_callback=progress)
        self.assertEqual(count, 1)
        self.assertEqual(session.rows[1].title, "Updated")
        self.assertEqual(session.commits, 2)
        self.assertEqual(updates[-1]["tasks_received"], 3)
        self.assertEqual(updates[-1]["tasks_saved"], 1)
        self.assertEqual(updates[-1]["tasks_created"], 1)
        self.assertEqual(updates[-1]["task_pages"], 2)
        self.assertEqual(updates[-1]["task_queries_done"], 1)
        self.assertEqual(updates[-1]["task_request_state"], "completed")
        fractions = [row["task_fraction"] for row in updates]
        self.assertEqual(fractions, sorted(fractions))

    async def test_second_page_failure_keeps_first_page_and_reports_retry(self):
        session = PageSession(deals=[100])
        api = AsyncMock(side_effect=[{"result": {"tasks": [{"id": "1", "title": "Saved", "ufCrmTask": ["D_100"]}]}, "next": 50},
                                    httpx.RemoteProtocolError("Disconnected"), httpx.RemoteProtocolError("Disconnected"),
                                    httpx.RemoteProtocolError("Disconnected")])
        updates = []
        async def progress(values):
            updates.append(values)
        with patch("cr_portal.services.task_sync.asyncio.sleep", AsyncMock()):
            with self.assertRaises(httpx.RemoteProtocolError):
                await sync_reporting_tasks(session, Obj(call=api), progress_callback=progress)
        self.assertIn(1, session.rows)
        self.assertEqual(session.commits, 1)
        self.assertEqual(updates[-1]["task_request_state"], "retrying")
        self.assertEqual(updates[-1]["tasks_saved"], 1)
        self.assertEqual(api.await_count, 4)

    async def test_roles_are_unchanged_and_existing_tasks_are_updated(self):
        person = Obj(bitrix_id=7, full_name="Developer", department_name="Разработка 1С")
        session = PageSession(people=[person])
        session.rows[1] = BitrixTask(bitrix_id=1, title="Old")
        api = AsyncMock(return_value={"result": {"tasks": [{"id": "1", "title": "New"}]}})
        progress = AsyncMock()
        count = await sync_reporting_tasks(session, Obj(call=api), progress_callback=progress)
        self.assertEqual(count, 1)
        self.assertEqual([call.args[1]["filter"] for call in api.await_args_list],
                         [{"RESPONSIBLE_ID": 7}, {"CREATED_BY": 7}, {"AUDITOR": 7}])
        self.assertEqual(progress.await_args.args[0]["tasks_created"], 0)
        self.assertEqual(session.rows[1].title, "New")

    async def test_invalid_pagination_fails_instead_of_looping_forever(self):
        api = AsyncMock(return_value={"result": {"tasks": []}, "next": 0})
        with self.assertRaisesRegex(RuntimeError, "pagination"):
            await sync_reporting_tasks(PageSession(deals=[100]), Obj(call=api))
        api.assert_awaited_once()

    async def test_empty_scope(self):
        api = AsyncMock()
        self.assertEqual(await sync_reporting_tasks(PageSession(), Obj(call=api)), 0)
        api.assert_not_awaited()


class WorkerActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_stale_and_legacy_jobs_are_distinguished(self):
        now = datetime(2026, 10, 15, 12, tzinfo=UTC)
        jobs = [{"job_id": str(i), "status": "running", "heartbeat_supported": True,
                 "started_at": (now - timedelta(minutes=10)).isoformat()} for i in range(3)]
        jobs[2].pop("heartbeat_supported")
        redis = Obj(mget=AsyncMock(return_value=[(now - timedelta(seconds=5)).isoformat(),
                                                 (now - timedelta(seconds=61)).isoformat(), None]))
        rows = await with_job_activity(redis, jobs, now=now)
        self.assertEqual([r["worker_alive"] for r in rows], [True, False, None])

    async def test_heartbeat_writes_separate_key_and_can_be_cancelled(self):
        written = asyncio.Event()
        async def write(key, value, **kwargs):
            self.assertEqual(key, HEARTBEAT_PREFIX + "test")
            self.assertTrue(datetime.fromisoformat(value))
            written.set()
        redis = Obj(set=AsyncMock(side_effect=write))
        task = asyncio.create_task(job_heartbeat(redis, "test"))
        await asyncio.wait_for(written.wait(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        redis.set.assert_awaited_once()
