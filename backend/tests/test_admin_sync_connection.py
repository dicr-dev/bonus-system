import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI, HTTPException

from cr_portal.api.deps import current_user, db_session
from cr_portal.api.v1.auth import _save_installation
from cr_portal.api.v1.sync import router
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.integrations.bitrix.oauth import refresh_installation_token
from cr_portal.integrations.bitrix.sync_connection import create_sync_client, ensure_sync_access, validate_sync_endpoint
from cr_portal.models.oauth import BitrixInstallation, BitrixSyncConnection

DATA = {"access_token": "admin-access", "refresh_token": "admin-refresh",
        "member_id": "test-portal", "domain": "example.test", "client_endpoint": "https://example.test/rest/"}


def connection():
    return BitrixSyncConnection(member_id="test-portal", admin_bitrix_user_id=1,
                               access_token="old-access", refresh_token="old-refresh",
                               client_endpoint="https://example.test/rest/", portal_domain="example.test",
                               verified_at=datetime.now(UTC))


class AdminConnectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        portal = patch("cr_portal.integrations.bitrix.sync_connection.settings.BITRIX_BASE_URL", "https://example.test")
        portal.start()
        self.addCleanup(portal.stop)

    async def test_untrusted_install_endpoint_is_rejected_before_remote_call(self):
        for endpoint in ("https://evil.invalid/rest/", "http://example.test/rest/", "https://example.test:444/rest/",
                         "https://example.test/rest/?auth=other", "https://user:pass@example.test/rest/"):
            with self.assertRaises(RuntimeError):
                validate_sync_endpoint(endpoint)

    async def test_install_writes_only_dedicated_table_and_pins_admin(self):
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: None)),
                      commit=AsyncMock(), refresh=AsyncMock(), add=MagicMock())
        with patch("cr_portal.api.v1.auth.ensure_sync_access", AsyncMock(return_value={"ID": "7", "ADMIN": True})):
            saved = await _save_installation(session, DATA)
        self.assertIsInstance(saved, BitrixSyncConnection)
        self.assertEqual(saved.admin_bitrix_user_id, 7)
        query = str(session.execute.await_args.args[0])
        self.assertIn("bitrix_sync_connections", query)
        self.assertNotIn("bitrix_installations", query)
        session.add.assert_called_once_with(saved)

    async def test_employee_install_cannot_replace_admin_tokens(self):
        saved = connection()
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: saved)), commit=AsyncMock())
        with patch("cr_portal.integrations.bitrix.client.BitrixClient.call", AsyncMock(return_value={"result": {"ID": "10542", "ADMIN": False}})):
            with self.assertRaises(HTTPException) as raised:
                await _save_installation(session, DATA)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual((saved.access_token, saved.refresh_token), ("old-access", "old-refresh"))
        session.execute.assert_not_awaited()
        session.commit.assert_not_awaited()

    async def test_reconnect_requires_new_pair_not_old_refresh_token(self):
        session = Obj(execute=AsyncMock())
        with patch("cr_portal.api.v1.auth.ensure_sync_access", AsyncMock(return_value={"ID": "7", "ADMIN": True})):
            with self.assertRaises(HTTPException):
                await _save_installation(session, {**DATA, "refresh_token": ""})
        session.execute.assert_not_awaited()

    async def test_default_save_cannot_change_owner_without_explicit_authorization(self):
        saved = connection()
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: saved)), commit=AsyncMock())
        with patch("cr_portal.api.v1.auth.ensure_sync_access", AsyncMock(return_value={"ID": "7", "ADMIN": True})):
            with self.assertRaises(HTTPException) as raised:
                await _save_installation(session, DATA)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(saved.admin_bitrix_user_id, 1)
        self.assertEqual(saved.access_token, "old-access")
        session.commit.assert_not_awaited()

    async def test_same_admin_can_renew_tokens_without_changing_owner(self):
        saved = connection()
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: saved)),
                      commit=AsyncMock(), refresh=AsyncMock())
        with patch("cr_portal.api.v1.auth.ensure_sync_access", AsyncMock(return_value={"ID": "1", "ADMIN": True})):
            await _save_installation(session, DATA)
        self.assertEqual(saved.admin_bitrix_user_id, 1)
        self.assertEqual(saved.access_token, DATA["access_token"])
        session.commit.assert_awaited_once()

    async def test_owner_can_change_only_with_explicit_authorization(self):
        saved = connection()
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: saved)),
                      commit=AsyncMock(), refresh=AsyncMock())
        with patch("cr_portal.api.v1.auth.ensure_sync_access", AsyncMock(return_value={"ID": "7", "ADMIN": True})):
            await _save_installation(session, DATA, allow_admin_change=True)
        self.assertEqual(saved.admin_bitrix_user_id, 7)
        session.commit.assert_awaited_once()

    async def test_factory_verifies_pinned_administrator_before_returning_client(self):
        saved = connection()
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: saved)))
        with patch("cr_portal.integrations.bitrix.client.BitrixClient.call", AsyncMock(return_value={"result": {"ID": "1", "ADMIN": True}})) as profile:
            client = await create_sync_client(session)
        self.assertIs(client.installation, saved)
        profile.assert_awaited_once_with("profile")
        self.assertEqual(client.webhook, "")

    async def test_persistent_client_rejects_legacy_storage_before_any_request(self):
        with self.assertRaises(RuntimeError):
            BitrixClient(installation=BitrixInstallation())

    async def test_expected_user_must_stay_administrator(self):
        for profile in ({"ID": "1", "ADMIN": False}, {"ID": "7", "ADMIN": True}, {"ADMIN": True}):
            with self.subTest(profile=profile):
                client = Obj(installation=connection(), call=AsyncMock(return_value={"result": profile}))
                with self.assertRaises(RuntimeError):
                    await ensure_sync_access(client)

    async def test_webhook_cannot_override_sync_or_login_credentials(self):
        with patch("cr_portal.integrations.bitrix.client.settings") as config:
            config.BITRIX_WEBHOOK_URL = "https://example.test/rest/employee/webhook"
            config.BITRIX_BASE_URL = "https://example.test"
            client = BitrixClient(installation=connection(), client_endpoint=DATA["client_endpoint"])
            login = BitrixClient(access_token="employee-access", client_endpoint=DATA["client_endpoint"], oauth_only=True)
        self.assertEqual(client.webhook, "")
        self.assertEqual(login.webhook, "")

    async def refresh(self, saved, profile, *, payload=None):
        session = Obj(refresh=AsyncMock(), commit=AsyncMock())
        response = MagicMock(is_error=False)
        response.json.return_value = payload or {"access_token": "new-access", "refresh_token": "new-refresh", "member_id": "test-portal"}
        http = AsyncMock()
        http.get.return_value = response
        with patch("cr_portal.integrations.bitrix.oauth.httpx.AsyncClient") as factory, \
             patch("cr_portal.integrations.bitrix.client.BitrixClient.call", AsyncMock(return_value={"result": profile})):
            factory.return_value.__aenter__.return_value = http
            try:
                await refresh_installation_token(session, saved)
            except RuntimeError as error:
                return session, error
        return session, None

    async def test_refresh_non_admin_is_rejected_before_tokens_are_mutated(self):
        saved = connection()
        session, error = await self.refresh(saved, {"ID": "10542", "ADMIN": False})
        self.assertIsNotNone(error)
        self.assertEqual((saved.access_token, saved.refresh_token), ("old-access", "old-refresh"))
        session.commit.assert_not_awaited()

    async def test_refresh_different_admin_is_also_rejected(self):
        saved = connection()
        session, error = await self.refresh(saved, {"ID": "7", "ADMIN": True})
        self.assertIsNotNone(error)
        self.assertEqual(saved.refresh_token, "old-refresh")
        session.commit.assert_not_awaited()

    async def test_refresh_same_admin_commits_verified_pair(self):
        saved = connection()
        session, error = await self.refresh(saved, {"ID": "1", "ADMIN": True})
        self.assertIsNone(error)
        self.assertEqual((saved.access_token, saved.refresh_token), ("new-access", "new-refresh"))
        session.commit.assert_awaited_once()
        self.assertEqual(session.refresh.await_args_list[0].kwargs, {"with_for_update": True})

    async def test_refresh_cannot_switch_portal(self):
        saved = connection()
        session, error = await self.refresh(saved, {"ID": "1", "ADMIN": True},
            payload={"access_token": "new-access", "refresh_token": "new-refresh", "member_id": "other-portal"})
        self.assertIsNotNone(error)
        self.assertEqual(saved.access_token, "old-access")
        session.commit.assert_not_awaited()

    async def test_legacy_credentials_cannot_be_refreshed_into_sync_connection(self):
        session = Obj(refresh=AsyncMock(), commit=AsyncMock())
        with self.assertRaises(RuntimeError):
            await refresh_installation_token(session, BitrixInstallation())
        session.refresh.assert_not_awaited()

    async def test_missing_trusted_connection_does_not_fall_back_to_legacy(self):
        from cr_portal.api.deps import bitrix_client
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: None)))
        with self.assertRaises(HTTPException) as raised:
            await bitrix_client(session)
        self.assertEqual(raised.exception.status_code, 503)
        query = str(session.execute.await_args.args[0])
        self.assertIn("bitrix_sync_connections", query)
        self.assertNotIn("bitrix_installations", query)

    async def test_public_connection_status_contains_no_tokens(self):
        app = FastAPI()
        app.include_router(router, prefix="/sync")
        saved = connection()
        session = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: saved)))
        app.dependency_overrides[db_session] = lambda: session
        app.dependency_overrides[current_user] = lambda: Obj(is_admin=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sync/connection")
            app.dependency_overrides[current_user] = lambda: Obj(is_admin=False)
            self.assertEqual((await client.get("/sync/connection")).status_code, 403)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"configured", "admin_bitrix_user_id", "verified_at"})
        self.assertNotIn("old-access", response.text)
        self.assertNotIn("old-refresh", response.text)
