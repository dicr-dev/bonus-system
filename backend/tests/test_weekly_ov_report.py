import unittest
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from cr_portal.services.deal_analytics import weekly_ov_report


class WeeklyOvReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_marks_new_current_and_successfully_transferred_deals(self):
        employee = SimpleNamespace(id=uuid4(), full_name="Сотрудник")
        def deal(bitrix_id, created, status="in_progress", closed=None):
            return SimpleNamespace(
                id=uuid4(), bitrix_id=bitrix_id, funnel="implementation", created_time=created,
                closed_time=closed, updated_time=created, status=status, module_name="Логистика",
                implementation_responsible_user_id=employee.id, title=f"Сделка {bitrix_id}",
                salesperson_name="Продавец", opportunity=100, machines_count=2,
                stage_title="В работе", stage_id="STAGE", raw_json="{}",
            )
        start = datetime(2026, 4, 6, 0, tzinfo=UTC)
        rows = [
            deal(1, start),
            deal(2, datetime(2026, 4, 1, tzinfo=UTC)),
            deal(3, datetime(2026, 4, 2, tzinfo=UTC), "won", datetime(2026, 4, 10, tzinfo=UTC)),
            deal(4, datetime(2026, 4, 7, tzinfo=UTC), "won", datetime(2026, 4, 11, tzinfo=UTC)),
        ]
        session = SimpleNamespace(execute=AsyncMock(side_effect=[
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows)),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [employee])),
        ]))

        with patch(
            "cr_portal.services.deal_analytics.get_business_settings",
            AsyncMock(return_value=SimpleNamespace(field_deal_current_status="CURRENT_STATUS")),
        ):
            result = await weekly_ov_report(session, date(2026, 4, 6), date(2026, 4, 12))

        self.assertEqual({row["bitrix_id"]: row["movement_status"] for row in result}, {
            1: "1. Новый", 2: "2. Текущий", 3: "3. Передали", 4: "1. Новый, 3. Передали",
        })
        self.assertEqual([row["bitrix_id"] for row in result], [1, 4, 2, 3])
