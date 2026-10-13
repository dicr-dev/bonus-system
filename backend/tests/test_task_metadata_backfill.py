import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cr_portal.models.task import BitrixTask
from cr_portal.services.task_metadata_backfill import backfill_task_metadata


class TaskMetadataBackfillTests(unittest.IsolatedAsyncioTestCase):
    async def test_restores_cards_but_does_not_erase_still_unavailable_metadata(self):
        missing = BitrixTask(bitrix_id=1, title="Название задачи недоступно в Bitrix", raw_json="{}")
        preserved = BitrixTask(bitrix_id=2, title="Known", crm_deal_ids_json="[25]", raw_json=json.dumps({"TITLE": "Known", "UF_CRM_TASK": ["D_25"], "metadata_source": "user_confirmed"}))
        result = SimpleNamespace(scalars=lambda: [missing, preserved])
        session = SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock())
        client = SimpleNamespace(call=AsyncMock(return_value={"result": {"fields": {"ID": {}, "TITLE": {}, "UF_CRM_TASK": {}}}}))
        progress = AsyncMock()
        with patch("cr_portal.services.task_metadata_backfill.tasks_by_id", AsyncMock(return_value={"1": {"ID": "1", "TITLE": "Recovered", "UF_CRM_TASK": ["D_10"]}})):
            stats = await backfill_task_metadata(session, client, progress)
        self.assertEqual(stats, {"total": 2, "restored": 1, "unavailable": 1, "unavailable_ids": [2]})
        self.assertEqual(missing.title, "Recovered")
        self.assertEqual(json.loads(missing.crm_deal_ids_json), [10])
        self.assertEqual(preserved.title, "Known")
        self.assertEqual(json.loads(preserved.crm_deal_ids_json), [25])
        progress.assert_awaited_once_with("task_metadata", 2, 100)


if __name__ == "__main__":
    unittest.main()
