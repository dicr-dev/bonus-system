import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from cr_portal.schemas.kpi import KPISummary
from cr_portal.services.bitrix_sync import sync_users
from cr_portal.services.employee_scope import (
    eligible_bonus_users,
    employee_is_in_kpi_department,
    kpi_department_name_from_user_data,
)
from cr_portal.services.kpi import ensure_kpi_event, kpi_summary
from cr_portal.services.subscriptions import SubscriptionDeals


class KPIDepartmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_kpi_fact_is_sum_of_dashboard_subscription_deals(self):
        implementation = SimpleNamespace(
            id=uuid4(), bitrix_id=101, title="Внедрение", opportunity=Decimal("120000")
        )
        cr_start = SimpleNamespace(
            id=uuid4(), bitrix_id=102, title="CR Start", opportunity=Decimal("30000")
        )
        plan_result = SimpleNamespace(
            scalar_one_or_none=lambda: SimpleNamespace(plan_value=Decimal("200000"))
        )
        session = SimpleNamespace(execute=AsyncMock(return_value=plan_result))

        with (
            patch("cr_portal.services.kpi.get_business_settings", AsyncMock(return_value=object())),
            patch(
                "cr_portal.services.kpi.subscription_deals_for_month",
                AsyncMock(return_value=SubscriptionDeals([implementation], [cr_start])),
            ),
            patch(
                "cr_portal.services.kpi.planned_subscription_deals_for_month",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await kpi_summary(session, datetime(2026, 8, 1).date())

        self.assertEqual(result["plan"], Decimal("200000"))
        self.assertEqual(result["fact"], Decimal("150000"))
        self.assertEqual(result["plan_completion_percent"], Decimal("75"))
        self.assertEqual(result["implementation_total"], Decimal("120000"))
        self.assertEqual(result["cr_start_total"], Decimal("30000"))
        self.assertEqual(result["implementation_deals"][0]["bitrix_id"], 101)
        self.assertEqual(result["cr_start_deals"][0]["bitrix_id"], 102)
        self.assertEqual(KPISummary.model_validate(result).fact, Decimal("150000"))

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

    def test_bonus_users_are_active_and_in_configured_departments(self):
        eligible = SimpleNamespace(
            id="eligible", is_active=True, department_name="Отдел внедрения"
        )
        wrong_department = SimpleNamespace(
            id="wrong", is_active=True, department_name="Отдел сопровождения"
        )
        inactive = SimpleNamespace(
            id="inactive", is_active=False, department_name="Разработка 1С"
        )

        self.assertEqual(
            eligible_bonus_users([eligible, wrong_department, inactive]),
            [eligible],
        )

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
