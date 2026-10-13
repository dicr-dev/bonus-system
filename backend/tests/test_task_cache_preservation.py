import json
import unittest
from datetime import datetime, timezone

from cr_portal.models.task import BitrixTask
from cr_portal.services.task_sync import _apply_task_sync_result


class TaskCachePreservationTests(unittest.TestCase):
    def test_missing_api_card_preserves_cached_title_link_and_snapshot(self):
        raw = json.dumps({"ID": "178630", "TITLE": "Компания. ЭТРН", "UF_CRM_TASK": ["D_50163"]})
        task = BitrixTask(bitrix_id=178630, title="Компания. ЭТРН", crm_deal_ids_json="[50163]", raw_json=raw)
        _apply_task_sync_result(task, {"ID": "178630", "TITLE": "Название задачи недоступно в Bitrix"}, datetime.now(timezone.utc), available=False)
        self.assertEqual(task.title, "Компания. ЭТРН")
        self.assertEqual(task.crm_deal_ids_json, "[50163]")
        self.assertEqual(task.raw_json, raw)

    def test_available_card_can_change_title_and_remove_crm_link(self):
        task = BitrixTask(bitrix_id=178630, title="Old", crm_deal_ids_json="[50163]", raw_json="{}")
        _apply_task_sync_result(task, {"ID": "178630", "TITLE": "New", "UF_CRM_TASK": []}, datetime.now(timezone.utc), available=True)
        self.assertEqual(task.title, "New")
        self.assertEqual(task.crm_deal_ids_json, "[]")

    def test_new_unavailable_task_still_gets_a_placeholder_for_time_entries(self):
        task = BitrixTask(bitrix_id=178630, title="")
        _apply_task_sync_result(task, {"ID": "178630", "TITLE": "Unavailable"}, datetime.now(timezone.utc), available=False)
        self.assertEqual(task.title, "Unavailable")
        self.assertEqual(task.crm_deal_ids_json, "[]")


if __name__ == "__main__":
    unittest.main()
