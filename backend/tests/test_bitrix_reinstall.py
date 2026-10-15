import unittest
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI

from cr_portal.api.deps import db_session
from cr_portal.api.v1.auth import router
from cr_portal.models.oauth import BitrixSyncConnection


class BitrixReinstallTests(unittest.IsolatedAsyncioTestCase):
    async def install(self, admin, *, user_id="1", existing=None):
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: existing)),
                      add=MagicMock(), commit=AsyncMock(), refresh=AsyncMock())
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/auth")
        app.dependency_overrides[db_session] = lambda: session
        with patch("cr_portal.integrations.bitrix.sync_connection.settings.BITRIX_BASE_URL", "https://example.test"), \
             patch("cr_portal.integrations.bitrix.client.BitrixClient.call", AsyncMock(return_value={"result": {"ID": user_id if admin else "10542", "ADMIN": admin}})):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/api/v1/auth/bitrix/install", data={
                    "AUTH_ID": "test-access", "REFRESH_ID": "test-refresh", "AUTH_EXPIRES": "3600",
                    "member_id": "test-portal", "DOMAIN": "example.test",
                })
        return session, response

    async def test_reinstall_saves_administrator_without_separate_connect_action(self):
        session, response = await self.install(True)
        self.assertEqual(response.status_code, 200)
        saved = session.add.call_args.args[0]
        self.assertIsInstance(saved, BitrixSyncConnection)
        self.assertEqual(saved.admin_bitrix_user_id, 1)
        self.assertEqual(saved.access_token, "test-access")
        self.assertEqual(saved.refresh_token, "test-refresh")
        session.commit.assert_awaited_once()
        self.assertIn("Административный доступ для синхронизации сохранён", response.text)
        self.assertNotIn("test-access", response.text)
        self.assertNotIn("test-refresh", response.text)

    async def test_non_admin_reinstall_does_not_write_credentials(self):
        session, response = await self.install(False)
        self.assertEqual(response.status_code, 403)
        session.execute.assert_not_awaited()
        session.add.assert_not_called()
        session.commit.assert_not_awaited()

    async def test_explicit_admin_reinstall_can_replace_old_administrator(self):
        saved = BitrixSyncConnection(member_id="test-portal", admin_bitrix_user_id=1,
                                    access_token="old-access", refresh_token="old-refresh")
        session, response = await self.install(True, user_id="7", existing=saved)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved.admin_bitrix_user_id, 7)
        self.assertEqual(saved.access_token, "test-access")
        self.assertEqual(saved.refresh_token, "test-refresh")
        session.add.assert_not_called()
        session.commit.assert_awaited_once()
