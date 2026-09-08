import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from cr_portal.services.bonus import cr_start_override_applies


class CrStartOverrideTests(unittest.TestCase):
    def test_three_month_override_applies_from_selected_month(self):
        event = SimpleNamespace(
            event_date=date(2026, 7, 1),
            quantity=Decimal("3"),
        )

        self.assertFalse(cr_start_override_applies(event, date(2026, 6, 1)))
        self.assertTrue(cr_start_override_applies(event, date(2026, 7, 1)))
        self.assertTrue(cr_start_override_applies(event, date(2026, 8, 1)))
        self.assertTrue(cr_start_override_applies(event, date(2026, 9, 1)))
        self.assertFalse(cr_start_override_applies(event, date(2026, 10, 1)))


if __name__ == "__main__":
    unittest.main()
