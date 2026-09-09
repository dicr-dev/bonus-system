import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from cr_portal.services.bonus import (
    MANUAL_AMOUNT_MODE,
    cr_start_fixed_amount,
    cr_start_override_applies,
)


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

    def test_manual_override_amount_is_a_direct_payment(self):
        override = SimpleNamespace(
            amount=Decimal("12500.50"),
            calculation_mode=MANUAL_AMOUNT_MODE,
        )

        self.assertEqual(
            cr_start_fixed_amount(override, {"cr_start_fixed": "10000"}),
            Decimal("12500.50"),
        )
        self.assertEqual(
            cr_start_fixed_amount(None, {"cr_start_fixed": "10000"}),
            Decimal("10000"),
        )

    def test_formula_override_uses_the_global_fixed_bonus(self):
        override = SimpleNamespace(
            amount=Decimal("12500.50"),
            calculation_mode="formula",
        )

        self.assertEqual(
            cr_start_fixed_amount(override, {"cr_start_fixed": "10000"}),
            Decimal("10000"),
        )


if __name__ == "__main__":
    unittest.main()
