import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from cr_portal.api.v1.calculations import _bonus_totals_by_calculation


class CalculationTotalsTests(unittest.IsolatedAsyncioTestCase):
    async def test_kpi_uses_dividable_subtotal_and_item_totals_after_divider(self):
        calculation_id = uuid4()
        calculation = SimpleNamespace(
            id=calculation_id,
            implementation_total=Decimal("675190.00"),
            subtotal_dividable=Decimal("109743.00"),
        )
        rows = [
            (calculation_id, "current_client", False, Decimal("52000.00"), Decimal("1")),
            (calculation_id, "training", True, Decimal("800.00"), Decimal("1")),
            (calculation_id, "support_hours", True, Decimal("3160.00"), Decimal("15.8")),
            (calculation_id, "implementation", True, Decimal("38011.20"), Decimal("1")),
            (calculation_id, "cr_start_implementation", True, Decimal("1926.00"), Decimal("1")),
        ]
        result = SimpleNamespace(all=lambda: rows)
        session = SimpleNamespace(execute=AsyncMock(return_value=result))

        totals = await _bonus_totals_by_calculation(session, [calculation])

        self.assertEqual(totals[calculation_id]["kpi_total"], Decimal("109743.00"))
        self.assertEqual(totals[calculation_id]["kpi_divided_total"], Decimal("43897.20"))
        self.assertEqual(totals[calculation_id]["current_client_total"], Decimal("52000.00"))


if __name__ == "__main__":
    unittest.main()
