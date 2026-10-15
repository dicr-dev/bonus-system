import json
import unittest
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx

from cr_portal.services.bitrix_sync import sync_deal_stage_history
from cr_portal.workers.sync import process_job


def result(rows):
    return Obj(scalars=lambda: rows)


class HistoryRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def run_history(self, responses, existing=(), deals=1):
        cards = [Obj(id=uuid4(), bitrix_id=index) for index in range(deals)]
        session = Obj(execute=AsyncMock(side_effect=[result(cards), result(existing), result(())]),
                      commit=AsyncMock(), add=lambda item: None)
        client = Obj(call_all=AsyncMock(side_effect=responses))
        progress = AsyncMock()
        with patch("cr_portal.services.bitrix_sync.get_business_settings", AsyncMock()), \
             patch("cr_portal.services.bitrix_sync.funnels", return_value={1: "implementation"}), \
             patch("cr_portal.services.bitrix_sync.get_stage_metadata", AsyncMock(return_value={})), \
             patch("cr_portal.services.bitrix_sync.asyncio.sleep", AsyncMock()) as sleep:
            try:
                count = await sync_deal_stage_history(session, client, progress_callback=progress)
            except httpx.TransportError:
                return session, client, progress, sleep, None
        return session, client, progress, sleep, count

    async def test_transient_disconnect_is_retried_and_duplicate_events_skipped(self):
        event = {"ID": "1", "CREATED_TIME": "2026-09-01T00:00:00+03:00", "CATEGORY_ID": "1", "STAGE_ID": "WON"}
        session, client, progress, sleep, count = await self.run_history(
            [httpx.RemoteProtocolError("Disconnected"), [event, event]], existing=[1])
        self.assertEqual(count, 0)
        self.assertEqual(client.call_all.await_count, 2)
        sleep.assert_awaited_once_with(1)
        progress.assert_awaited_once_with(1, 1)
        self.assertGreaterEqual(session.commit.await_count, 1)

    async def test_finished_deal_remains_committed_if_later_requests_fail(self):
        event = {"ID": "1", "CREATED_TIME": "2026-09-01T00:00:00+03:00", "CATEGORY_ID": "1", "STAGE_ID": "WON"}
        session, client, progress, sleep, count = await self.run_history(
            [[event], httpx.RemoteProtocolError("Disconnected"), httpx.RemoteProtocolError("Disconnected"),
             httpx.RemoteProtocolError("Disconnected")], deals=2)
        self.assertIsNone(count)
        self.assertEqual(session.commit.await_count, 1)
        progress.assert_awaited_once_with(1, 2)
        self.assertEqual(client.call_all.await_count, 4)


class RecoveryJobTests(unittest.IsolatedAsyncioTestCase):
    async def test_recovery_does_not_reload_users_or_deals(self):
        data = {"job_id": "test", "type": "reporting_resume", "full": True, "status": "queued"}
        redis = Obj(get=AsyncMock(side_effect=lambda *args: json.dumps(data)),
                    set=AsyncMock(side_effect=lambda key, value, **kwargs: data.update(json.loads(value))))
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: Obj(access_token="test", client_endpoint="https://example.invalid/rest/"))))
        context = AsyncMock()
        context.__aenter__.return_value = session
        with patch("cr_portal.workers.sync.async_session_factory", return_value=context), \
             patch("cr_portal.workers.sync.create_sync_client", AsyncMock()) as create_client, \
             patch("cr_portal.workers.sync.sync_deal_stage_history", AsyncMock(return_value=2)) as history, \
             patch("cr_portal.workers.sync.sync_reporting_tasks", AsyncMock(return_value=3)) as tasks, \
             patch("cr_portal.workers.sync.sync_task_1c_errors", AsyncMock()) as types, \
             patch("cr_portal.workers.sync.refresh_report_fields", AsyncMock()) as fields, \
             patch("cr_portal.workers.sync.sync_users", AsyncMock()) as users, \
             patch("cr_portal.workers.sync.sync_deals", AsyncMock()) as deals:
            await process_job(redis, "test")
        for called in (history, tasks, types, fields):
            called.assert_awaited_once()
        users.assert_not_awaited()
        deals.assert_not_awaited()
        create_client.assert_awaited_once_with(session)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["processed"], 5)
