import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from cr_portal.api.deps import current_user
from cr_portal.api.v1.auth import (
    _public_frontend_url,
    _resolve_current_user,
    bitrix_app,
)
from cr_portal.core.config import settings


class BitrixAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_inactive_user_cannot_use_existing_session(self):
        request = SimpleNamespace(session={"bitrix_user_id": 10401})
        session = SimpleNamespace()
        with patch("cr_portal.api.deps.UserRepository") as repository_class:
            repository_class.return_value.by_bitrix_id = AsyncMock(
                return_value=SimpleNamespace(is_active=False)
            )
            with self.assertRaises(HTTPException) as raised:
                await current_user(request, session)
        self.assertEqual(raised.exception.status_code, 401)

    def test_public_frontend_uses_https_origin_from_callback(self):
        request = SimpleNamespace(
            headers={"host": "backend:8000"},
            url=SimpleNamespace(scheme="http"),
        )
        with patch.object(
            settings,
            "BITRIX_REDIRECT_URI",
            "https://public.example.test/api/v1/auth/bitrix/callback",
        ):
            self.assertEqual(
                _public_frontend_url(request),
                "https://public.example.test/",
            )

    async def test_current_employee_is_saved_after_bitrix_login(self):
        installation = SimpleNamespace(
            access_token="access-token",
            client_endpoint="https://example.bitrix24.test/rest/",
        )
        session = SimpleNamespace(commit=AsyncMock())
        employee = SimpleNamespace(id="employee-id", bitrix_id=10401)

        with (
            patch("cr_portal.api.v1.auth.BitrixClient") as client_class,
            patch("cr_portal.api.v1.auth.UserRepository") as repository_class,
        ):
            client_class.return_value.call = AsyncMock(return_value={
                "result": {
                    "ID": "10401",
                    "NAME": "Максим",
                    "LAST_NAME": "Бочкарев",
                    "EMAIL": "employee@example.test",
                    "WORK_POSITION": "Специалист отдела внедрения",
                    "UF_DEPARTMENT": [20],
                }
            })
            repository_class.return_value.upsert = AsyncMock(return_value=employee)

            result = await _resolve_current_user(session, installation)

        self.assertIs(result, employee)
        repository_class.return_value.upsert.assert_awaited_once_with(
            bitrix_id=10401,
            email="employee@example.test",
            full_name="Максим Бочкарев",
            position="Специалист отдела внедрения",
            department_name="Отдел внедрения",
        )
        session.commit.assert_awaited_once()

    async def test_bitrix_app_redirects_to_public_frontend(self):
        request = SimpleNamespace(session={})
        installation = SimpleNamespace(
            access_token="access-token",
            refresh_token="refresh-token",
            client_endpoint="https://example.bitrix24.test/rest/",
        )
        employee = SimpleNamespace(bitrix_id=10401)

        with (
            patch("cr_portal.api.v1.auth._read_request_data", AsyncMock(return_value={})),
            patch("cr_portal.api.v1.auth._exchange_authorization_code", AsyncMock(return_value={})),
            patch("cr_portal.api.v1.auth._save_installation", AsyncMock(return_value=installation)),
            patch("cr_portal.api.v1.auth._resolve_current_user", AsyncMock(return_value=employee)),
            patch("cr_portal.api.v1.auth._public_frontend_url", return_value="https://public.example.test/"),
        ):
            response = await bitrix_app(request, SimpleNamespace())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "https://public.example.test/")
        self.assertEqual(request.session["bitrix_user_id"], 10401)


if __name__ == "__main__":
    unittest.main()
