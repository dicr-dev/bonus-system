import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from cr_portal.services.subscriptions import planned_subscription_deals_for_month


class PlannedSubscriptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_planned_deals_use_configured_date_and_month(self):
        field = "ufCrm_1774423053267"
        deals = [
            SimpleNamespace(
                id=uuid4(), bitrix_id=2, raw_json=json.dumps({field: "2026-09-20"})
            ),
            SimpleNamespace(
                id=uuid4(), bitrix_id=1, raw_json=json.dumps({field: "2026-09-10"})
            ),
            SimpleNamespace(
                id=uuid4(), bitrix_id=3, raw_json=json.dumps({field: "2026-10-01"})
            ),
        ]
        result = SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: deals),
        )
        session = SimpleNamespace(execute=AsyncMock(return_value=result))
        business = SimpleNamespace(field_planned_subscription_date=field)

        planned = await planned_subscription_deals_for_month(
            session,
            business,
            date(2026, 9, 1),
        )

        self.assertEqual([item.deal.bitrix_id for item in planned], [1, 2])
        self.assertEqual(planned[0].planned_date, date(2026, 9, 10))
        query = session.execute.await_args.args[0]
        self.assertIn("deals.status", str(query.whereclause))


if __name__ == "__main__":
    unittest.main()
