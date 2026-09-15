import unittest
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from cr_portal.services.time_report import time_spent_report


class TimeReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_aggregates_task_time_once_for_selected_funnel(self):
        user = SimpleNamespace(
            id=uuid4(), bitrix_id=10, full_name="Сотрудник", department_name="Отдел внедрения",
            is_active=True, is_admin=True,
        )
        task = SimpleNamespace(
            bitrix_id=20, title="Задача", group_id=None, responsible_bitrix_id=10,
            crm_deal_ids_json="[100, 200]",
        )
        first = SimpleNamespace(user_bitrix_id=10, task_bitrix_id=20, seconds=3600, created_time=datetime(2026, 9, 2, 8, tzinfo=UTC))
        second = SimpleNamespace(user_bitrix_id=10, task_bitrix_id=20, seconds=1800, created_time=datetime(2026, 9, 2, 9, tzinfo=UTC))
        deal = SimpleNamespace(bitrix_id=100, funnel="implementation")
        session = SimpleNamespace(execute=AsyncMock(side_effect=[
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [user])),
            SimpleNamespace(all=lambda: [(first, task), (second, task)]),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [deal])),
        ]))

        result = await time_spent_report(
            session, date_from=date(2026, 9, 2), date_to=date(2026, 9, 2),
            departments=[], employee_ids=[], funnels=["implementation"], current_user=user,
        )

        self.assertEqual(result["employees"][0]["total_seconds"], 5400)
        self.assertEqual(result["employees"][0]["days"][0]["tasks"][0]["seconds"], 5400)
