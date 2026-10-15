import json
import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI

from cr_portal.api.deps import bitrix_client, current_user, db_session
from cr_portal.api.v1.monthly_rating import router
from cr_portal.services.monthly_rating import (
    TYPE_LABEL, build_monthly_rating, month_bounds, refresh_type_metadata,
)


def user(bitrix_id=1, department="Отдел внедрения", active=True):
    return Obj(id=uuid4(), bitrix_id=bitrix_id, full_name=f"Сотрудник {bitrix_id}",
               department_name=department, is_active=active)


def deal(owner=None, *, bitrix_id=100, amount="1000", funnel="implementation", status="won",
         closed="2026-09-15T12:00:00+03:00", integration=True):
    return Obj(bitrix_id=bitrix_id, title=f"Сделка {bitrix_id}", opportunity=Decimal(amount),
               funnel=funnel, status=status, closed_time=datetime.fromisoformat(closed) if closed else None,
               implementation_responsible_user_id=owner.id if owner else None, integration_1c=integration)


def task(owner=2, *, bitrix_id=200, deals=(100,), status=5, closed="2026-09-15T12:00:00+03:00", value="42"):
    return Obj(bitrix_id=bitrix_id, title=f"Задача {bitrix_id}", responsible_bitrix_id=owner, group_id=None,
               status=status, closed_time=datetime.fromisoformat(closed) if closed else None,
               crm_deal_ids_json=json.dumps(deals), raw_json=json.dumps({"ufTypeTask1c": value}))


def report(users=(), deals=(), tasks=(), elapsed=(), **kwargs):
    return build_monthly_rating(users, deals, tasks, elapsed, month="2026-09",
                                type_field="UF_TYPE_TASK_1C", labels=kwargs.get("labels", {"42": TYPE_LABEL, "43": "Другое"}))


class MonthlyRatingTests(unittest.TestCase):
    def test_all_active_employees_and_only_correct_department(self):
        a, b = user(), user(2)
        result = report([a, b, user(3, active=False), user(4, "Другой отдел"), user(5, "Разработка 1С")])
        self.assertEqual(len(result["implementation"]), 2)
        self.assertEqual(len(result["development"]), 1)
        self.assertTrue(all(row["deal_count"] == 0 for row in result["implementation"]))

    def test_successful_implementation_sum_not_subscription_and_descending(self):
        a, b = user(), user(2)
        deals = [deal(a, amount="1.15"), deal(a, bitrix_id=101, amount="2.25"), deal(b, amount="12"),
                 deal(a, status="lost"), deal(a, status="in_progress"), deal(a, funnel="cr_start"),
                 deal(a, funnel="support"), deal(a, funnel="tech_integration", integration=False)]
        rows = report([a, b], deals)["implementation"]
        self.assertEqual([row["deal_amount"] for row in rows], ["12", "3.40"])
        self.assertEqual(rows[1]["deal_count"], 2)
        self.assertEqual(len(rows[1]["deals"]), 2)

    def test_moscow_month_boundaries_for_closure(self):
        a = user()
        deals = [deal(a, closed="2026-08-31T21:00:00+00:00"),
                 deal(a, closed="2026-09-30T20:59:59+00:00"),
                 deal(a, closed="2026-09-30T21:00:00+00:00"),
                 deal(a, closed="2026-08-31T20:59:59+00:00"), deal(a, closed=None)]
        self.assertEqual(report([a], deals)["implementation"][0]["deal_count"], 2)

    def test_task_completion_not_creation_and_actual_log_author(self):
        a, b = user(2, "Разработка 1С"), user(3, "Разработка 1С")
        tasks = [task(), task(status=2), task(closed="2026-08-01T00:00:00+03:00"),
                 task(owner=3, closed="2026-08-31T21:00:00+00:00")]
        logs = [Obj(user_bitrix_id=3, seconds=3600, created_time=datetime.fromisoformat("2026-08-31T21:00:00+00:00")),
                Obj(user_bitrix_id=3, seconds=1800, created_time=datetime.fromisoformat("2026-09-15T00:00:00+03:00")),
                Obj(user_bitrix_id=2, seconds=7200, created_time=datetime.fromisoformat("2026-09-30T21:00:00+00:00"))]
        rows = {row["bitrix_id"]: row for row in report([a, b], tasks=tasks, elapsed=logs)["development"]}
        self.assertEqual(rows[2]["task_count"], 1)
        self.assertEqual(rows[3]["task_count"], 1)
        self.assertEqual(rows[3]["hours"], "1.50")
        self.assertEqual(rows[2]["hours"], "0.00")

    def test_same_deal_same_developer_multiple_tasks_counts_once(self):
        a = user(2, "Разработка 1С")
        tasks = [task(closed="2026-07-01T00:00:00+03:00"), task(bitrix_id=201, status=2, closed=None)]
        result = report([a], [deal(funnel="tech_integration")], tasks)
        self.assertEqual(result["development"][0]["integration_count"], 1)
        self.assertEqual(result["integration_issues"], [])

    def test_multiple_developers_not_counted_and_all_tasks_in_warning(self):
        users = [user(2, "Разработка 1С"), user(3, "Разработка 1С")]
        tasks = [task(), task(owner=3, bitrix_id=201)]
        result = report(users, [deal(funnel="tech_integration")], tasks)
        self.assertTrue(all(row["integration_count"] == 0 for row in result["development"]))
        self.assertEqual([row["bitrix_id"] for row in result["integration_issues"][0]["tasks"]], [200, 201])

    def test_inactive_owner_still_detects_ambiguity_but_not_in_rating(self):
        users = [user(2, "Разработка 1С"), user(3, "Разработка 1С", active=False)]
        result = report(users, [deal(funnel="tech_integration")], [task(), task(owner=3, bitrix_id=201)])
        self.assertEqual(len(result["development"]), 1)
        self.assertIn("Разные исполнители", result["integration_issues"][0]["reason"])

    def test_only_won_tech_with_1c_in_month_and_correct_type(self):
        a = user(2, "Разработка 1С")
        deals = [deal(funnel="tech_integration", status="lost"),
                 deal(funnel="tech_integration", integration=False),
                 deal(funnel="tech_integration", closed="2026-08-01T00:00:00+03:00"),
                 deal(bitrix_id=101, funnel="tech_integration")]
        result = report([a], deals, [task(), task(deals=(101,), value="43")])
        self.assertEqual(result["development"][0]["integration_count"], 0)
        self.assertEqual(len(result["integration_issues"]), 1)

    def test_missing_enum_is_not_misrepresented_as_zero(self):
        result = report([user(2, "Разработка 1С")], [deal(funnel="tech_integration")], [task()], labels={})
        self.assertFalse(result["integration_count_reliable"])
        self.assertIsNone(result["development"][0]["integration_count"])
        self.assertTrue(result["warnings"])

    def test_unrecognized_enum_blocks_integration_count(self):
        result = report([user(2, "Разработка 1С")], tasks=[task(value="999")])
        self.assertFalse(result["integration_count_reliable"])

    def test_malformed_payloads_do_not_break_other_metrics(self):
        t = task()
        t.raw_json = "broken"
        t.crm_deal_ids_json = "{}"
        result = report([user(2, "Разработка 1С")], tasks=[t])
        self.assertEqual(result["development"][0]["task_count"], 1)

    def test_invalid_months_and_december_rollover(self):
        for month in ("2026-13", "2026-00", "2026-9", "oops", "9999-12"):
            with self.assertRaises(ValueError):
                month_bounds(month)
        self.assertEqual(month_bounds("2026-12")[2].isoformat(), "2027-01-01T00:00:00+03:00")


class MonthlyRatingAccessTests(unittest.IsolatedAsyncioTestCase):
    def app(self, admin):
        app = FastAPI()
        app.include_router(router, prefix="/analytics")
        app.dependency_overrides[current_user] = lambda: Obj(is_admin=admin)
        app.dependency_overrides[db_session] = lambda: None
        self.bitrix = AsyncMock()
        app.dependency_overrides[bitrix_client] = self.bitrix
        return app

    async def test_employee_denied_view_and_metadata_refresh(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(False)), base_url="http://test") as client:
            self.assertEqual((await client.get("/analytics/monthly-rating")).status_code, 403)
            self.assertEqual((await client.post("/analytics/monthly-rating/type-metadata")).status_code, 403)
            self.bitrix.assert_not_awaited()

    async def test_admin_and_invalid_month(self):
        with patch("cr_portal.api.v1.monthly_rating.get_business_settings", AsyncMock(return_value=Obj())), \
             patch("cr_portal.api.v1.monthly_rating.monthly_rating_report", AsyncMock(return_value={"month": "2026-09"})) as service:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(True)), base_url="http://test") as client:
                self.assertEqual((await client.get("/analytics/monthly-rating?month=2026-09")).status_code, 200)
                self.assertEqual((await client.get("/analytics/monthly-rating?month=bad")).status_code, 422)
                service.side_effect = ValueError("Некорректный месяц")
                self.assertEqual((await client.get("/analytics/monthly-rating?month=2026-13")).status_code, 422)

    async def test_metadata_uses_real_enum_ids(self):
        client = Obj(call_all=AsyncMock(return_value=[{"ID": "123", "FIELD_NAME": "UF_TYPE_TASK_1C"}]),
                     call=AsyncMock(return_value={"result": {"LIST": [{"ID": "portal-id", "VALUE": TYPE_LABEL}]}}))
        session = Obj(get=AsyncMock(return_value=None), add=lambda row: None, commit=AsyncMock())
        result = await refresh_type_metadata(session, client, "UF_TYPE_TASK_1C")
        self.assertEqual(result["labels"], {"portal-id": TYPE_LABEL})
        client.call.assert_awaited_once_with("task.item.userfield.get", {"ID": "123"})
        session.commit.assert_awaited_once()

    async def test_missing_label_preserves_previous_metadata(self):
        client = Obj(call_all=AsyncMock(return_value=[{"ID": "123", "FIELD_NAME": "UF_TYPE_TASK_1C"}]),
                     call=AsyncMock(return_value={"result": {"LIST": [{"ID": "1", "VALUE": "Другое"}]}}))
        session = Obj(get=AsyncMock(), commit=AsyncMock())
        with self.assertRaises(ValueError):
            await refresh_type_metadata(session, client, "UF_TYPE_TASK_1C")
        session.commit.assert_not_awaited()
