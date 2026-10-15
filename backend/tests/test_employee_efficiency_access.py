import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from cr_portal.api.deps import current_user, db_session
from cr_portal.api.v1.employee_efficiency import router


class EmployeeEfficiencyAccessTests(unittest.IsolatedAsyncioTestCase):
    def app(self, admin):
        app = FastAPI()
        app.include_router(router, prefix="/analytics")
        app.dependency_overrides[current_user] = lambda: SimpleNamespace(is_admin=admin)
        app.dependency_overrides[db_session] = lambda: None
        return app

    async def test_employee_cannot_view_or_export_report(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(False)), base_url="http://test") as client:
            for path in ("/analytics/employee-efficiency", "/analytics/employee-efficiency/export"):
                response = await client.get(path)
                self.assertEqual(response.status_code, 403)

    async def test_admin_can_view_report_and_invalid_owner_is_rejected(self):
        with (
            patch("cr_portal.api.v1.employee_efficiency.get_business_settings", AsyncMock(return_value=SimpleNamespace())),
            patch("cr_portal.api.v1.employee_efficiency.employee_efficiency_report", AsyncMock(return_value={"employees": [], "warnings": []})) as report,
        ):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(True)), base_url="http://test") as client:
                response = await client.get("/analytics/employee-efficiency")
                self.assertEqual(response.status_code, 200)
                response = await client.get("/analytics/employee-efficiency", params={"employee_id": "invalid"})
                self.assertEqual(response.status_code, 422)
                report.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
