import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cr_portal.api.v1.calculations import list_calculations
from cr_portal.api.v1.reports import department


def empty_result():
    return SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=list),
    )


class EmployeeAccessScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_calculation_list_is_limited_to_current_employee(self):
        session = SimpleNamespace(execute=AsyncMock(return_value=empty_result()))
        user = SimpleNamespace(id="employee-id", is_admin=False)

        result = await list_calculations("2026-08", session, user)

        self.assertEqual(result, [])
        query = session.execute.await_args.args[0]
        self.assertIn("bonus_calculations.employee_id", str(query.whereclause))

    async def test_deal_list_is_limited_to_implementation_responsible(self):
        session = SimpleNamespace(execute=AsyncMock(return_value=empty_result()))
        user = SimpleNamespace(id="employee-id", is_admin=False)

        result = await department(user, session)

        self.assertEqual(result, [])
        query = session.execute.await_args.args[0]
        self.assertIn("deals.implementation_responsible_user_id", str(query.whereclause))


if __name__ == "__main__":
    unittest.main()
