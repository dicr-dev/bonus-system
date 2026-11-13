import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, HTTPException

from cr_portal.api.deps import current_user, db_session
from cr_portal.api.v1.reports import router
from cr_portal.services.task_1c_report import _display_type


class Task1CReportTests(unittest.IsolatedAsyncioTestCase):
    def app(self, department=None, admin=False, authenticated=True):
        app = FastAPI()
        app.include_router(router, prefix="/reports")

        async def user():
            if not authenticated:
                raise HTTPException(401, "Authentication required")
            return SimpleNamespace(is_admin=admin, department_name=department)

        app.dependency_overrides[current_user] = user
        app.dependency_overrides[db_session] = lambda: None
        return app

    async def test_access_for_both_departments_and_administrator(self):
        for department, admin, expected in (
            ("Отдел внедрения", False, 200),
            ("Разработка 1С", False, 200),
            ("Отдел сопровождения; Разработка 1С", False, 200),
            (None, True, 200),
            ("Отдел сопровождения", False, 403),
        ):
            with self.subTest(department=department, admin=admin):
                response_value = {"tasks": [], "developers": []}
                with patch(
                    "cr_portal.api.v1.reports.task_1c_report",
                    AsyncMock(return_value=response_value),
                ):
                    transport = httpx.ASGITransport(app=self.app(department, admin))
                    async with httpx.AsyncClient(
                        transport=transport, base_url="http://test"
                    ) as client:
                        response = await client.get("/reports/tasks-1c")
                self.assertEqual(response.status_code, expected, response.text)

    def test_type_display_keeps_actual_values(self):
        self.assertEqual(_display_type(["Ошибка", "Доработка"]), "Ошибка, Доработка")
        self.assertEqual(_display_type({"VALUE": "Консультация"}), "Консультация")
        self.assertIsNone(_display_type(None))


if __name__ == "__main__":
    unittest.main()
