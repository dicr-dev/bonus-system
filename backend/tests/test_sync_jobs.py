import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from cr_portal.api.deps import current_user
from cr_portal.api.v1.sync import router
from cr_portal.services.sync_jobs import JOB_PREFIX, list_sync_jobs


def job(number, status):
    return {"job_id": str(number), "type": "all", "status": status,
            "created_at": f"2026-10-15T10:{number:02}:00+00:00", "progress": 0}


class FakeRedis:
    def __init__(self, jobs):
        self.data = {JOB_PREFIX + str(index): json.dumps(value) for index, value in enumerate(jobs)}
        self.batches = []

    async def scan_iter(self, match, count):
        assert match == JOB_PREFIX + "*"
        for key in list(self.data):
            yield key

    async def mget(self, keys):
        self.batches.append(len(keys))
        return [self.data.get(key) for key in keys]


class SyncJobsTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_active_jobs_survive_new_request_and_recent_limit(self):
        redis = FakeRedis([job(1, "running"), job(2, "queued"), job(3, "completed"), job(4, "failed")])
        first = await list_sync_jobs(redis, recent_limit=1)
        second = await list_sync_jobs(redis, recent_limit=1)
        self.assertEqual(first, second)
        self.assertEqual([row["job_id"] for row in first], ["2", "1", "4"])

    async def test_no_active_jobs_returns_recent_results(self):
        result = await list_sync_jobs(FakeRedis([job(1, "completed"), job(2, "failed")]))
        self.assertEqual([row["status"] for row in result], ["failed", "completed"])

    async def test_expired_corrupt_and_non_job_values_ignored(self):
        redis = FakeRedis([job(1, "running"), {}, [], job(2, "unknown")])
        redis.data[JOB_PREFIX + "broken"] = "broken"
        redis.data[JOB_PREFIX + "expired"] = None
        self.assertEqual(len(await list_sync_jobs(redis)), 1)

    async def test_scan_duplicates_do_not_duplicate_cards(self):
        redis = FakeRedis([job(1, "running"), job(1, "running")])
        self.assertEqual(len(await list_sync_jobs(redis)), 1)

    async def test_batches_and_unlimited_active_jobs(self):
        redis = FakeRedis([job(index, "queued") for index in range(205)])
        result = await list_sync_jobs(redis)
        self.assertEqual(len(result), 205)
        self.assertEqual(redis.batches, [100, 100, 5])

    async def test_empty_redis(self):
        self.assertEqual(await list_sync_jobs(FakeRedis([])), [])


class SyncJobsAccessTests(unittest.IsolatedAsyncioTestCase):
    def app(self, admin):
        app = FastAPI()
        app.include_router(router, prefix="/sync")
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(is_admin=admin)
        return app

    async def test_employee_cannot_list_jobs(self):
        with patch("cr_portal.api.v1.sync.get_redis") as get_redis:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(False)), base_url="http://test") as client:
                self.assertEqual((await client.get("/sync/jobs")).status_code, 403)
            get_redis.assert_not_called()

    async def test_admin_restores_running_and_queued_on_repeated_page_load(self):
        redis = FakeRedis([job(1, "running"), job(2, "queued"), job(3, "failed")])
        with patch("cr_portal.api.v1.sync.get_redis", return_value=redis):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(True)), base_url="http://test") as client:
                for _ in range(2):
                    response = await client.get("/sync/jobs")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual([row["status"] for row in response.json()], ["queued", "running", "failed"])
