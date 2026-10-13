import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from cr_portal.api.v1.auth import _save_installation, bitrix_app, bitrix_callback
from cr_portal.integrations.bitrix.sync_connection import ensure_sync_access


DATA = {"access_token": "test-user-token", "refresh_token": "test-user-refresh", "member_id": "test-portal", "domain": "example.test"}


class OAuthIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_app_login_does_not_save_shared_credentials_or_tokens_in_cookie(self):
        request = SimpleNamespace(session={"bitrix_access_token": "old", "bitrix_refresh_token": "old"})
        with (
            patch("cr_portal.api.v1.auth._read_request_data", AsyncMock(return_value=DATA)),
            patch("cr_portal.api.v1.auth._exchange_authorization_code", AsyncMock(return_value=DATA)),
            patch("cr_portal.api.v1.auth._save_installation", AsyncMock()) as save,
            patch("cr_portal.api.v1.auth._resolve_current_user", AsyncMock(return_value=SimpleNamespace(bitrix_id=15))),
            patch("cr_portal.api.v1.auth._public_frontend_url", return_value="https://example.test/"),
            patch("cr_portal.api.v1.auth.enqueue_task_metadata_backfill", AsyncMock(return_value="test-job")),
        ):
            response = await bitrix_app(request, SimpleNamespace())
        save.assert_not_awaited()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(request.session["bitrix_user_id"], 15)
        self.assertNotIn("bitrix_access_token", request.session)
        self.assertNotIn("bitrix_refresh_token", request.session)

    async def callback(self, sync):
        request = SimpleNamespace(session={"bitrix_oauth_state": "test-state", "bitrix_oauth_sync": sync}, query_params={"state": "test-state", "code": "test-code"})
        response = MagicMock()
        response.json.return_value = DATA
        http = AsyncMock()
        http.get.return_value = response
        installation = SimpleNamespace(access_token="shared", client_endpoint="https://example.test/rest/")
        with (
            patch("cr_portal.api.v1.auth.httpx.AsyncClient") as factory,
            patch("cr_portal.api.v1.auth._save_installation", AsyncMock(return_value=installation)) as save,
            patch("cr_portal.api.v1.auth.enqueue_task_metadata_backfill", AsyncMock(return_value="test-job")),
            patch("cr_portal.api.v1.auth._resolve_current_user", AsyncMock(return_value=SimpleNamespace(id="test-user", bitrix_id=15))),
            patch("cr_portal.api.v1.auth._public_frontend_url", return_value="https://example.test/"),
        ):
            factory.return_value.__aenter__.return_value = http
            result = await bitrix_callback(request, SimpleNamespace())
        return save, result

    async def test_normal_callback_does_not_replace_shared_installation(self):
        save, response = await self.callback(False)
        save.assert_not_awaited()
        self.assertEqual(response.headers["location"], "https://example.test/")

    async def test_explicit_sync_callback_saves_shared_installation(self):
        save, response = await self.callback(True)
        save.assert_awaited_once()
        self.assertEqual(response.headers["location"], "https://example.test/sync?metadata_job=test-job")

    async def test_invalid_state_does_not_accept_sync_credentials(self):
        request = SimpleNamespace(session={"bitrix_oauth_state": "expected", "bitrix_oauth_sync": True}, query_params={"state": "wrong", "code": "code"})
        with self.assertRaises(HTTPException) as raised:
            await bitrix_callback(request, SimpleNamespace())
        self.assertEqual(raised.exception.status_code, 400)

    async def test_non_admin_installation_is_rejected_before_database_write(self):
        session = SimpleNamespace(execute=AsyncMock())
        with patch("cr_portal.api.v1.auth.ensure_sync_access", AsyncMock(side_effect=RuntimeError("Administrator required"))):
            with self.assertRaises(HTTPException) as raised:
                await _save_installation(session, DATA)
        self.assertEqual(raised.exception.status_code, 403)
        session.execute.assert_not_awaited()

    async def test_sync_access_checks_bitrix_admin_flag(self):
        for value in (False, "N", "false", None):
            client = SimpleNamespace(call=AsyncMock(return_value={"result": {"ID": "15", "ADMIN": value}}))
            with self.assertRaises(RuntimeError):
                await ensure_sync_access(client)
        client = SimpleNamespace(call=AsyncMock(return_value={"result": {"ID": "5", "ADMIN": True}}))
        self.assertEqual((await ensure_sync_access(client))["ID"], "5")


if __name__ == "__main__":
    unittest.main()
