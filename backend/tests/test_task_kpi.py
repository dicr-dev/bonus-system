import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.services.task_kpi import (
    in_month,
    overtime_hours,
    support_hour_contributions,
    task_contributions,
)


def config(**changes):
    values = dict(task_training_bonus_field="UF_TASK_BONUS", task_training_yes_value="783",
                  task_training_date_field="DEADLINE", overtime_project_id=192,
                  overtime_department_ids="20,33", task_overtime_hours_field="UF_HOURS",
                  overtime_time_priority="manual")
    return SimpleNamespace(**(values | changes))


class TaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_uses_oauth_server(self):
        from cr_portal.core.config import settings
        from cr_portal.integrations.bitrix.oauth import refresh_installation_token
        installation = SimpleNamespace(refresh_token="old-refresh", client_endpoint="https://example.test/rest/", portal_domain="example.test")
        response = httpx.Response(200, json={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}, request=httpx.Request("GET", settings.BITRIX_OAUTH_TOKEN_URL))
        with patch("cr_portal.integrations.bitrix.oauth.httpx.AsyncClient") as mocked:
            client = mocked.return_value.__aenter__.return_value
            client.get = AsyncMock(return_value=response)
            session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
            await refresh_installation_token(session, installation)
            self.assertEqual(client.get.call_args.args[0], settings.BITRIX_OAUTH_TOKEN_URL)
            self.assertEqual(installation.access_token, "new-access")
            self.assertEqual(installation.refresh_token, "new-refresh")
            session.commit.assert_awaited_once()

    def test_hours_priority_and_zero(self):
        task = {"ufHours": "0", "timeSpentInLogs": "5400"}
        self.assertEqual(overtime_hours(task, config()), (Decimal(0), "manual"))
        self.assertEqual(overtime_hours(task, config(overtime_time_priority="tracker")), (Decimal("1.5"), "tracker"))
        self.assertEqual(overtime_hours({"timeSpentInLogs": "5400"}, config())[0], Decimal("1.5"))
        for value in ["bad", "-1", "NaN", "Infinity"]:
            with self.assertRaises(ValueError):
                overtime_hours({"ufHours": value}, config())

    def test_month_boundaries_moscow(self):
        month = date(2026, 9, 1)
        self.assertTrue(in_month("2026-08-31T21:00:00Z", month))
        self.assertFalse(in_month("2026-09-30T21:00:00Z", month))
        self.assertFalse(in_month(None, month))

    async def test_task_pagination(self):
        client = BitrixClient()
        client.call = AsyncMock(side_effect=[{"result": {"tasks": [{"id": "1"}]}, "next": 50}, {"result": {"tasks": [{"id": "2"}]}}])
        self.assertEqual(await client.call_all("tasks.task.list", {}), [{"id": "1"}, {"id": "2"}])
        self.assertEqual(client.call.call_args.args[1]["start"], 50)

    async def test_training_flag_deadline_and_overtime_department(self):
        base = {"id": "1", "responsibleId": "10", "deadline": "2026-09-30T17:00:00+03:00", "closedDate": None,
                "ufTaskBonus": "783", "groupId": "192", "timeSpentInLogs": "5400"}
        client = SimpleNamespace(call_all=AsyncMock(side_effect=[
            [base, base, base | {"id": "2", "ufTaskBonus": "784"}, base | {"id": "3", "deadline": None}],
            [{"ID": "10"}], [],
            [base, base, base | {"id": "4", "responsibleId": "11"}, base | {"id": "5", "groupId": "142"}],
        ]))
        rows = await task_contributions(client, config(), date(2026, 9, 1),
                                        [SimpleNamespace(bitrix_id=10, id="employee")], {"training_bonus": "2000"})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1][1], "training")
        self.assertEqual(rows[0][1][5], Decimal(2000))
        self.assertEqual(rows[1][1][1], "overtime_hours")
        self.assertEqual(rows[1][1][4], Decimal("1.5"))
        self.assertEqual(rows[1][1][5], Decimal(0))
        self.assertIn(">=DEADLINE", client.call_all.call_args_list[0].args[1]["filter"])

    async def test_support_hours_are_grouped_by_task_and_time_author(self):
        first_page = [
            {"ID": str(i), "TASK_ID": "100", "USER_ID": "10", "SECONDS": "60",
             "CREATED_DATE": "2026-09-02T10:00:00+03:00"}
            for i in range(50)
        ]
        second_page = [
            {"ID": "51", "TASK_ID": "100", "USER_ID": "10", "SECONDS": "3540",
             "CREATED_DATE": "2026-09-03T10:00:00+03:00"},
            {"ID": "52", "TASK_ID": "100", "USER_ID": "11", "SECONDS": "1800",
             "CREATED_DATE": "2026-09-03T10:00:00+03:00"},
        ]
        task_response = {"result": {"tasks": [{
            "id": "100", "title": "Работа с клиентом", "ufCrmTask": ["D_500"],
            "responsibleId": "99", "groupId": "35",
        }]}}
        client = SimpleNamespace(call=AsyncMock(side_effect=[
            {"result": first_page}, {"result": second_page}, task_response,
        ]))
        support = SimpleNamespace(
            id="support", bitrix_id=500, status="in_progress",
            created_time=None, closed_time=None, updated_time=None,
        )
        implementation = SimpleNamespace(
            status="won", closed_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
            updated_time=None,
        )
        users = [
            SimpleNamespace(bitrix_id=10, id="employee-10"),
            SimpleNamespace(bitrix_id=11, id="employee-11"),
        ]

        rows = await support_hour_contributions(
            client, date(2026, 9, 1), users, {"support_hour_rate": "200"},
            [support], {support.id: [implementation]},
        )

        self.assertEqual(len(rows), 2)
        first = next(row for employee, row in rows if employee == "employee-10")
        self.assertEqual(first[1], "support_hours")
        self.assertEqual(first[4], Decimal("1.82"))
        self.assertEqual(first[5], Decimal("364.00"))
        self.assertEqual(first[8]["seconds"], 6540)
        self.assertEqual(first[8]["task_id"], "100")
        self.assertEqual(
            client.call.call_args_list[1].args[1]["PARAMS"]["NAV_PARAMS"]["iNumPage"],
            2,
        )

    async def test_time_after_lost_support_close_is_excluded(self):
        client = SimpleNamespace(call=AsyncMock(side_effect=[
            {"result": [{
                "ID": "1", "TASK_ID": "100", "USER_ID": "10", "SECONDS": "3600",
                "CREATED_DATE": "2026-09-03T10:00:00+03:00",
            }]},
            {"result": {"tasks": [{"id": "100", "ufCrmTask": ["D_500"]}]}},
        ]))
        support = SimpleNamespace(
            id="support", bitrix_id=500, status="lost", created_time=None,
            closed_time=datetime(2026, 9, 2, tzinfo=timezone.utc), updated_time=None,
        )
        implementation = SimpleNamespace(
            status="won", closed_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
            updated_time=None,
        )
        rows = await support_hour_contributions(
            client, date(2026, 9, 1), [SimpleNamespace(bitrix_id=10, id="employee")],
            {"support_hour_rate": "200"}, [support], {support.id: [implementation]},
        )
        self.assertEqual(rows, [])

    async def test_active_support_without_implementation_link_is_included(self):
        client = SimpleNamespace(call=AsyncMock(side_effect=[
            {"result": [{
                "ID": "75537", "TASK_ID": "178382", "USER_ID": "10401",
                "SECONDS": "57600", "CREATED_DATE": "2026-08-11T23:15:00+03:00",
            }]},
            {"result": {"tasks": [{
                "id": "178382", "title": "Контроль логистика",
                "ufCrmTask": ["D_46929"], "groupId": "158",
            }]}},
        ]))
        support = SimpleNamespace(
            id="support-46929", bitrix_id=46929, status="in_progress",
            created_time=datetime(2025, 3, 17, tzinfo=timezone.utc),
            closed_time=None, updated_time=None,
        )
        rows = await support_hour_contributions(
            client, date(2026, 8, 1),
            [SimpleNamespace(bitrix_id=10401, id="maxim")],
            {"support_hour_rate": "200"}, [support], {support.id: []},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "maxim")
        self.assertEqual(rows[0][1][4], Decimal("16.00"))
        self.assertEqual(rows[0][1][5], Decimal("3200.00"))

    async def test_tech_integration_hours_are_reference_only(self):
        client = SimpleNamespace(call=AsyncMock(side_effect=[
            {"result": [{
                "ID": "75495", "TASK_ID": "178378", "USER_ID": "10401",
                "SECONDS": "258600", "CREATED_DATE": "2026-08-03T22:33:00+03:00",
            }]},
            {"result": {"tasks": [{
                "id": "178378", "title": "ФККГрупп - вопросы по интеграции",
                "ufCrmTask": ["D_51532"], "groupId": "0",
            }]}},
        ]))
        tech_integration = SimpleNamespace(
            id="tech-51532", bitrix_id=51532, funnel="tech_integration", status="won",
            closed_time=datetime(2026, 7, 31, tzinfo=timezone.utc), updated_time=None,
        )
        rows = await support_hour_contributions(
            client, date(2026, 8, 1),
            [SimpleNamespace(bitrix_id=10401, id="maxim")],
            {"support_hour_rate": "200"}, [], {}, [tech_integration],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "maxim")
        self.assertEqual(rows[0][1][1], "task_hours_reference")
        self.assertEqual(rows[0][1][4], Decimal("71.83"))
        self.assertEqual(rows[0][1][5], Decimal("0"))
        self.assertFalse(rows[0][1][6])
        self.assertEqual(rows[0][1][8]["client_deal_funnel"], "tech_integration")

    async def test_development_employee_support_hours_are_reference_only(self):
        client = SimpleNamespace(call=AsyncMock(side_effect=[
            {"result": [{
                "ID": "1", "TASK_ID": "100", "USER_ID": "10", "SECONDS": "3600",
                "CREATED_DATE": "2026-09-03T10:00:00+03:00",
            }]},
            {"result": {"tasks": [{
                "id": "100", "title": "Работа с клиентом", "ufCrmTask": ["D_500"],
            }]}},
        ]))
        support = SimpleNamespace(
            id="support", bitrix_id=500, funnel="support", status="in_progress",
            created_time=None, closed_time=None, updated_time=None,
        )

        rows = await support_hour_contributions(
            client,
            date(2026, 9, 1),
            [SimpleNamespace(bitrix_id=10, id="developer")],
            {"support_hour_rate": "200"},
            [support],
            {support.id: []},
            paid_employee_ids=set(),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1][1], "task_hours_reference")
        self.assertEqual(rows[0][1][4], Decimal("1.00"))
        self.assertEqual(rows[0][1][5], Decimal("0"))
        self.assertFalse(rows[0][1][6])


if __name__ == "__main__":
    unittest.main()
