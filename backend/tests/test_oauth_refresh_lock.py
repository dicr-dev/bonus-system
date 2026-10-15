import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from cr_portal.integrations.bitrix.oauth import refresh_installation_token
from cr_portal.models.oauth import BitrixSyncConnection


class OAuthRefreshLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_worker_refreshes_current_locked_credentials(self):
        installation = BitrixSyncConnection(member_id="test-portal", admin_bitrix_user_id=7, refresh_token="stale-user-refresh", client_endpoint="https://example.test/rest/", portal_domain="example.test")

        async def refresh(instance, **kwargs):
            if kwargs.get("with_for_update"):
                instance.refresh_token = "current-sync-refresh"

        session = SimpleNamespace(refresh=AsyncMock(side_effect=refresh), commit=AsyncMock())
        response = MagicMock()
        response.is_error = False
        response.json.return_value = {"access_token": "new-sync-access", "refresh_token": "new-sync-refresh", "expires_in": 3600}
        http = AsyncMock()
        http.get.return_value = response
        with patch("cr_portal.integrations.bitrix.oauth.httpx.AsyncClient") as factory, \
             patch("cr_portal.integrations.bitrix.client.BitrixClient.call", AsyncMock(return_value={"result": {"ID": "7", "ADMIN": True}})):
            factory.return_value.__aenter__.return_value = http
            await refresh_installation_token(session, installation)
        self.assertEqual(http.get.call_args.kwargs["params"]["refresh_token"], "current-sync-refresh")
        self.assertEqual(session.refresh.call_args_list[0].kwargs, {"with_for_update": True})
        self.assertEqual(installation.access_token, "new-sync-access")
        self.assertEqual(installation.refresh_token, "new-sync-refresh")


if __name__ == "__main__":
    unittest.main()
