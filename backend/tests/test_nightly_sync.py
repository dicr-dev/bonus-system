import unittest
from datetime import UTC, date, datetime

from cr_portal.services.task_sync import task_sync_window
from cr_portal.workers.sync import daily_calculation_due, nightly_sync_due


class NightlySyncTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
