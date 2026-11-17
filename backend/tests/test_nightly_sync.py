import json
import unittest
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cr_portal.services.task_sync import task_sync_window
from cr_portal.workers.sync import (
    NIGHTLY_LAST_RESULT_KEY,
    daily_calculation_due,
    nightly_sync_due,
    process_nightly_sync,
    task_1c_report_sync_due,
)


class NightlySyncTests(unittest.IsolatedAsyncioTestCase):
    def test_task_window_includes_current_and_previous_month(self):
        self.assertEqual(
            task_sync_window(datetime(2026, 9, 8, tzinfo=UTC), months=2),
            (date(2026, 8, 1), date(2026, 10, 1)),
        )

    def test_task_window_crosses_year_boundary(self):
        self.assertEqual(
            task_sync_window(datetime(2026, 1, 15, tzinfo=UTC), months=3),
            (date(2025, 11, 1), date(2026, 2, 1)),
        )

    def test_nightly_run_starts_after_configured_hour(self):
        self.assertFalse(
            nightly_sync_due(
                datetime(2026, 9, 7, 22, 59, tzinfo=UTC),
                last_success=None,
                last_attempt=None,
                hour=2,
                timezone_name="Europe/Moscow",
            )
        )
        self.assertTrue(
            nightly_sync_due(
                datetime(2026, 9, 7, 23, 0, tzinfo=UTC),
                last_success=None,
                last_attempt=None,
                hour=2,
                timezone_name="Europe/Moscow",
            )
        )

    def test_success_today_prevents_duplicate_run(self):
        self.assertFalse(
            nightly_sync_due(
                datetime(2026, 9, 8, 8, 0, tzinfo=UTC),
                last_success="2026-09-07T23:30:00+00:00",
                last_attempt="2026-09-07T23:00:00+00:00",
                hour=2,
                timezone_name="Europe/Moscow",
            )
        )

    def test_failed_run_is_retried_after_one_hour(self):
        now = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)
        self.assertFalse(
            nightly_sync_due(
                now,
                last_success=None,
                last_attempt="2026-09-08T07:30:00+00:00",
                hour=2,
                timezone_name="Europe/Moscow",
            )
        )
        self.assertTrue(
            nightly_sync_due(
                now,
                last_success=None,
                last_attempt="2026-09-08T06:59:59+00:00",
                hour=2,
                timezone_name="Europe/Moscow",
            )
        )

    def test_daily_calculation_runs_once_after_three_moscow(self):
        before_three = datetime(2026, 9, 7, 23, 59, tzinfo=UTC)
        at_three = datetime(2026, 9, 8, 0, 0, tzinfo=UTC)
        self.assertFalse(
            daily_calculation_due(
                before_three,
                last_success=None,
                last_attempt=None,
                hour=3,
                timezone_name="Europe/Moscow",
            )
        )
        self.assertTrue(
            daily_calculation_due(
                at_three,
                last_success=None,
                last_attempt=None,
                hour=3,
                timezone_name="Europe/Moscow",
            )
        )
        self.assertFalse(
            daily_calculation_due(
                datetime(2026, 9, 8, 6, 0, tzinfo=UTC),
                last_success="2026-09-08T00:30:00+00:00",
                last_attempt="2026-09-08T00:00:00+00:00",
                hour=3,
                timezone_name="Europe/Moscow",
            )
        )

    def test_task_1c_report_sync_runs_every_thirty_minutes(self):
        now = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)
        self.assertTrue(task_1c_report_sync_due(now, last_success=None))
        self.assertFalse(task_1c_report_sync_due(now, last_success="2026-09-08T07:31:00+00:00"))
        self.assertTrue(task_1c_report_sync_due(now, last_success="2026-09-08T07:30:00+00:00"))

    async def test_nightly_sync_updates_stage_history_and_reports_count(self):
        redis=AsyncMock()
        redis.set.return_value=True
        redis.get.return_value=None
        session=object()
        context=AsyncMock()
        context.__aenter__.return_value=session
        with patch("cr_portal.workers.sync.async_session_factory",return_value=context), \
             patch("cr_portal.workers.sync.create_sync_client",AsyncMock(return_value="client")), \
             patch("cr_portal.workers.sync.sync_users",AsyncMock(return_value=2)), \
             patch("cr_portal.workers.sync.sync_deals",AsyncMock(return_value=3)), \
             patch("cr_portal.workers.sync.sync_deal_stage_history",AsyncMock(return_value=4)) as history, \
             patch("cr_portal.workers.sync.get_business_settings",AsyncMock(return_value=SimpleNamespace(field_training_video="VIDEO"))), \
             patch("cr_portal.workers.sync.discover_training_videos",AsyncMock(return_value=5)), \
             patch("cr_portal.workers.sync.sync_tasks",AsyncMock(return_value={"tasks":6})), \
             patch("cr_portal.workers.sync.sync_task_1c_errors",AsyncMock(return_value={"task_1c_errors":7})):
            self.assertTrue(await process_nightly_sync(redis))

        history.assert_awaited_once_with(session,"client")
        payload=next(call.args[1] for call in redis.set.await_args_list if call.args[0]==NIGHTLY_LAST_RESULT_KEY)
        self.assertEqual(json.loads(payload)["stage_history"],4)


if __name__ == "__main__":
    unittest.main()
