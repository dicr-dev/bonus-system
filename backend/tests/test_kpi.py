import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cr_portal.services.bitrix_sync import sync_users
from cr_portal.services.kpi import (
    employee_is_in_kpi_department,
    ensure_kpi_event,
    kpi_department_name_from_user_data,
)


class KPIDepartmentTests(unittest.IsolatedAsyncioTestCase):
    def test_bitrix_department_ids_are_mapped_to_kpi_departments(self):
        self.assertEqual(
            kpi_department_name_from_user_data({"UF_DEPARTMENT": [20, 33]}),
            "Отдел внедрения; Разработка 1С",
        )
        self.assertIsNone(
            kpi_department_name_from_user_data({"UF_DEPARTMENT": [25]})
        )

    def test_only_configured_departments_are_eligible(self):
        self.assertTrue(employee_is_in_kpi_department(
            SimpleNamespace(department_name="Отдел внедрения")
        ))
        self.assertTrue(employee_is_in_kpi_department(
            SimpleNamespace(department_name="Отдел внедрения; Разработка 1С")
        ))
        self.assertFalse(employee_is_in_kpi_department(
            SimpleNamespace(department_name="Отдел сопровождения")
        ))
        self.assertFalse(employee_is_in_kpi_department(None))

    async def test_user_sync_keeps_only_kpi_departments(self):
        client = SimpleNamespace(call_all=AsyncMock(side_effect=[
            [
                {"ID": "1", "NAME": "Компания"},
                {"ID": "20", "NAME": "Отдел внедрения"},
                {"ID": "33", "NAME": "Разработка 1С"},
                {"ID": "25", "NAME": "Отдел сопровождения"},
            ],
            [{
                "ID": "5",
                "NAME": "Дамир",
                "LAST_NAME": "Искандеров",
                "UF_DEPARTMENT": [1, 20, 33, 25],
                "ACTIVE": "Y",
            }],
        ]))
        session = SimpleNamespace(commit=AsyncMock())

        with patch("cr_portal.services.bitrix_sync.UserRepository") as repository_class:
            repository_class.return_value.upsert = AsyncMock(
                return_value=SimpleNamespace(is_active=False)
            )
            count = await sync_users(session, client)

        self.assertEqual(count, 1)
        self.assertEqual(
            repository_class.return_value.upsert.await_args.kwargs["department_name"],
            "Отдел внедрения; Разработка 1С",
        )
        session.commit.assert_awaited_once()

    async def test_existing_kpi_event_gets_missing_employee(self):
        event = SimpleNamespace(employee_id=None)
        session = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(
                scalar_one_or_none=lambda: event
            )),
            add=lambda value: None,
        )
        deal = SimpleNamespace(
            status="won",
            funnel="implementation",
            closed_time=datetime(2026, 8, 10, tzinfo=timezone.utc),
            bitrix_id=123,
            implementation_responsible_user_id="employee-id",
            id="deal-id",
        )

        await ensure_kpi_event(session, deal)

        self.assertEqual(event.employee_id, "employee-id")


if __name__ == "__main__":
    unittest.main()
