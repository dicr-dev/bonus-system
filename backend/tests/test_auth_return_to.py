import unittest
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from cr_portal.api.v1.auth import _safe_return_path, _start_oauth, bitrix_callback


class ReturnPathTests(unittest.TestCase):
    def test_local_ui_paths_preserved(self):
        for path in ("/", "/analytics/weekly-ov", "/analytics/weekly-ov?date_from=2026-10-19#details"):
            self.assertEqual(_safe_return_path(path), path)

    def test_external_encoded_and_auth_targets_rejected(self):
        for path in (None, "", "https://evil.test", "//evil.test", "/\\evil.test", "/%2f/evil.test",
                     "/%252f/evil.test", "/%5cevil.test", "/%0d%0aLocation:evil", "/api/v1/auth/bitrix/login",
                     "\n/analytics/weekly-ov", " /analytics/weekly-ov", "/"+"x"*2048):
            with self.subTest(path=path):
                self.assertEqual(_safe_return_path(path), "/")

    def test_return_path_saved_in_oauth_session_not_bitrix_authorize_url(self):
        request=Obj(session={},query_params={"return_to":"/analytics/weekly-ov"})
        with patch("cr_portal.api.v1.auth.settings.BITRIX_CLIENT_ID","test-client"), \
             patch("cr_portal.api.v1.auth.settings.BITRIX_REDIRECT_URI","https://portal.test/api/v1/auth/bitrix/callback"):
            response=_start_oauth(request,sync=False)
        self.assertEqual(request.session['bitrix_oauth_return_to'],'/analytics/weekly-ov')
        self.assertNotIn('return_to',response.headers['location'])
        self.assertFalse(request.session['bitrix_oauth_sync'])


class CallbackReturnTests(unittest.IsolatedAsyncioTestCase):
    async def callback(self, target, sync=False):
        request=Obj(session={'bitrix_oauth_state':'test-state','bitrix_oauth_sync':sync,
                             'bitrix_oauth_return_to':target},
                    query_params={'state':'test-state','code':'test-code'})
        token_response=Obj(raise_for_status=lambda:None,json=lambda:{'access_token':'test-only','member_id':'test'})
        client=MagicMock()
        client.__aenter__=AsyncMock(return_value=Obj(get=AsyncMock(return_value=token_response)))
        client.__aexit__=AsyncMock(return_value=None)
        employee=Obj(id=uuid4(),bitrix_id=14567)
        with patch('cr_portal.api.v1.auth.httpx.AsyncClient',return_value=client), \
             patch('cr_portal.api.v1.auth._login_context',return_value=Obj()), \
             patch('cr_portal.api.v1.auth._save_installation',AsyncMock(return_value=Obj())) as save, \
             patch('cr_portal.api.v1.auth._resolve_current_user',AsyncMock(return_value=employee)), \
             patch('cr_portal.api.v1.auth._public_frontend_url',return_value='https://portal.test/'), \
             patch('cr_portal.api.v1.auth.enqueue_task_metadata_backfill',AsyncMock(return_value='test-job')):
            response=await bitrix_callback(request,None)
        self.assertNotIn('bitrix_oauth_return_to',request.session)
        self.assertEqual(request.session['bitrix_user_id'],14567)
        self.assertEqual(save.await_count,1 if sync else 0)
        return response

    async def test_employee_returns_to_report_without_saving_sync_tokens(self):
        response=await self.callback('/analytics/weekly-ov')
        self.assertEqual(response.headers['location'],'https://portal.test/analytics/weekly-ov')

    async def test_invalid_return_stays_on_portal(self):
        response=await self.callback('//evil.test')
        self.assertEqual(response.headers['location'],'https://portal.test/')

    async def test_sync_flow_still_returns_to_sync_page(self):
        response=await self.callback('/analytics/weekly-ov',sync=True)
        self.assertEqual(response.headers['location'],'https://portal.test/sync?metadata_job=test-job')

    async def test_invalid_state_still_rejected(self):
        request=Obj(session={'bitrix_oauth_state':'expected','bitrix_oauth_return_to':'/analytics/weekly-ov'},
                    query_params={'state':'wrong','code':'test-code'})
        with self.assertRaises(HTTPException) as caught:
            await bitrix_callback(request,None)
        self.assertEqual(caught.exception.status_code,400)
