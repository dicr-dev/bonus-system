import unittest
from unittest.mock import AsyncMock

from cr_portal.services.task_kpi import tasks_by_id


class TaskTitlesTests(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_list_from_bulk_task_request(self):
        client = type("Client", (), {})()
        client.call = AsyncMock(return_value={
            "result": [{"id": "1", "title": "Task one"}],
        })

        result = await tasks_by_id(client, ["1"])

        self.assertEqual(result["1"]["title"], "Task one")
        self.assertEqual(client.call.await_count, 1)

    async def test_retries_missing_bulk_task_by_id(self):
        client = type("Client", (), {})()
        client.call = AsyncMock(side_effect=[
            {"result": {"tasks": [{"id": "1", "title": "Первая"}]}},
            {"result": {"task": {"id": "2", "title": "Вторая"}}},
        ])

        result = await tasks_by_id(client, ["1", "2"])

        self.assertEqual(result["1"]["title"], "Первая")
        self.assertEqual(result["2"]["title"], "Вторая")
        self.assertEqual(client.call.await_count, 2)

    async def test_accepts_list_from_single_task_request(self):
        client = type("Client", (), {})()
        client.call = AsyncMock(side_effect=[
            {"result": {"tasks": []}},
            {"result": [{"id": "2", "title": "Task two"}]},
        ])

        result = await tasks_by_id(client, ["2"])

        self.assertEqual(result["2"]["title"], "Task two")
