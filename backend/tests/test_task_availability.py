import json
import unittest
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, patch

import httpx

from cr_portal.models.task import BitrixTask, BitrixTaskElapsedItem
from cr_portal.services.task_kpi import tasks_by_id
from cr_portal.services.task_sync import _apply_task_sync_result, sync_tasks


class TaskAvailabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_successful_empty_get_confirms_unavailable(self):
        for response in ({"result": []}, {"result": {"task": None}}, {"result": {"task": {}}}):
            missing=set()
            client=Obj(call=AsyncMock(side_effect=[{"result":{"tasks":[]}},response]))
            cards=await tasks_by_id(client,["182043"],unavailable_ids=missing)
            self.assertEqual(cards,{})
            self.assertEqual(missing,{"182043"})

    async def test_timeout_and_malformed_response_do_not_confirm_unavailable(self):
        for response in (httpx.ReadTimeout("timeout"), {"result":None}, {"result":{}}, {"result":"invalid"}):
            missing=set()
            client=Obj(call=AsyncMock(side_effect=[{"result":{"tasks":[]}},response]))
            self.assertEqual(await tasks_by_id(client,["182043"],unavailable_ids=missing),{})
            self.assertEqual(missing,set())

    async def test_batch_failure_aborts_without_marking_tasks(self):
        missing=set()
        client=Obj(call=AsyncMock(side_effect=httpx.ConnectError("offline")))
        with self.assertRaises(httpx.ConnectError):
            await tasks_by_id(client,["182043"],unavailable_ids=missing)
        self.assertEqual(missing,set())

    async def test_individual_fallback_finds_card(self):
        missing=set()
        client=Obj(call=AsyncMock(side_effect=[{"result":{"tasks":[]}},
                                             {"result":{"task":{"id":"182043","title":"Recovered"}}}]))
        self.assertIn("182043",await tasks_by_id(client,["182043"],unavailable_ids=missing))
        self.assertFalse(missing)

    def test_unavailable_card_retains_snapshot_and_can_be_restored(self):
        now=datetime.now(UTC)
        task=BitrixTask(bitrix_id=182043,title="Known",crm_deal_ids_json="[53899]",raw_json='{"ID":"182043"}')
        _apply_task_sync_result(task,{},now,available=False,confirmed_unavailable=True)
        self.assertFalse(task.api_available)
        self.assertEqual(task.title,"Known")
        self.assertEqual(task.raw_json,'{"ID":"182043"}')
        self.assertEqual(task.crm_deal_ids_json,"[53899]")
        _apply_task_sync_result(task,{"ID":"182043","TITLE":"Recovered","UF_CRM_TASK":["D_53899"]},
                                now+timedelta(seconds=1),available=True)
        self.assertTrue(task.api_available)

    def test_uncertain_check_does_not_change_existing_availability(self):
        now=datetime.now(UTC)
        task=BitrixTask(bitrix_id=1,title="Known",raw_json="{}",api_available=True,api_checked_at=now)
        _apply_task_sync_result(task,{},now+timedelta(seconds=1),available=False)
        self.assertTrue(task.api_available)
        self.assertEqual(task.api_checked_at,now)

    def test_older_check_cannot_replace_a_newer_availability(self):
        now=datetime.now(UTC)
        task=BitrixTask(bitrix_id=1,title="Known",raw_json="{}",api_available=True,api_checked_at=now)
        _apply_task_sync_result(task,{},now-timedelta(seconds=1),available=False,confirmed_unavailable=True)
        self.assertTrue(task.api_available)

    async def test_sync_keeps_orphan_elapsed_record_but_marks_task(self):
        now=datetime(2026,10,16,14,11,55,tzinfo=UTC)
        task=BitrixTask(bitrix_id=182043,title="Known",raw_json='{"ID":"182043"}',crm_deal_ids_json="[53899]")
        entry=BitrixTaskElapsedItem(bitrix_id=78310,task_bitrix_id=182043,user_bitrix_id=15,
                                   seconds=3596400,created_time=now,raw_json="{}")
        rows=lambda values:Obj(scalars=lambda:values)
        session=Obj(execute=AsyncMock(side_effect=[rows([task]),rows([entry]),None]),
                    flush=AsyncMock(),commit=AsyncMock(),add=lambda row:self.fail("Existing history must not be replaced"))
        payload={"ID":"78310","TASK_ID":"182043","USER_ID":"15","SECONDS":"3596400",
                 "CREATED_DATE":now.isoformat()}
        client=Obj(call=AsyncMock(side_effect=[{"result":{"tasks":[]}},{"result":[]}]))
        with patch("cr_portal.services.task_sync.elapsed_items_between",AsyncMock(return_value=[payload])), \
             patch("cr_portal.services.task_sync._relevant_task_ids",AsyncMock(return_value=(["182043"],[]))):
            await sync_tasks(session,client,start_date=date(2026,10,16),end_date=date(2026,10,17))
        self.assertFalse(task.api_available)
        self.assertEqual(task.title,"Known")
        self.assertEqual(entry.seconds,3596400)
        self.assertEqual(entry.task_bitrix_id,182043)
        session.commit.assert_awaited_once()
