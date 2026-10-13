import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from cr_portal.services.bonus import implementation_bonus_stopped


class LostSupportBonusTests(unittest.TestCase):
    def setUp(self):
        self.implementation = SimpleNamespace(bitrix_id=48100, module_name="ТМ")
        self.support = SimpleNamespace(
            status="lost", module_name="ТМ",
            raw_json=json.dumps({"source": ["D_48100"]}),
            closed_time=datetime(2026, 9, 28, tzinfo=timezone.utc),
            updated_time=datetime(2026, 10, 5, tzinfo=timezone.utc),
        )

    def stopped(self, year, month):
        end = datetime(year, month, 1, tzinfo=timezone.utc)
        return implementation_bonus_stopped(self.implementation, [self.support], "source", end)

    def test_stops_in_loss_month_and_later_but_preserves_previous_month(self):
        self.assertFalse(self.stopped(2026, 9))
        self.assertTrue(self.stopped(2026, 10))
        self.assertTrue(self.stopped(2026, 11))

    def test_uses_closed_time_before_latest_edit_date(self):
        self.assertTrue(self.stopped(2026, 10))

    def test_falls_back_to_updated_time_if_closed_time_missing(self):
        self.support.closed_time = None
        self.assertFalse(self.stopped(2026, 10))
        self.assertTrue(self.stopped(2026, 11))

    def test_active_support_does_not_stop_payout(self):
        self.support.status = "in_progress"
        self.assertFalse(self.stopped(2026, 10))

    def test_another_link_or_module_does_not_stop_payout(self):
        self.support.module_name = "Логистика"
        self.assertFalse(self.stopped(2026, 10))
        self.support.module_name = "ТМ"
        self.support.raw_json = json.dumps({"source": ["D_123"]})
        self.assertFalse(self.stopped(2026, 10))

    def test_loss_at_next_month_boundary_does_not_change_previous_month(self):
        self.support.closed_time = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.assertFalse(self.stopped(2026, 10))


if __name__ == "__main__":
    unittest.main()
