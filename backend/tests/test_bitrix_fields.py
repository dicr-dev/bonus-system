import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cr_portal.api.v1.settings import list_bitrix_deal_fields
from cr_portal.schemas.app_settings import AppSettingsPayload


class BitrixFieldsTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_only_custom_deal_fields_with_titles(self):
        client = SimpleNamespace(call=AsyncMock(return_value={"result": {"fields": {
            "id": {"title": "ID", "type": "integer"},
            "ufCrm_100": {"title": "Дата начала списаний", "type": "date"},
            "UFCRM_200": {"listLabel": "Направление", "type": "enumeration"},
        }}}))

        fields = await list_bitrix_deal_fields(client=client)

        self.assertEqual([field["code"] for field in fields], ["ufCrm_100", "UFCRM_200"])
        self.assertEqual(fields[0]["title"], "Дата начала списаний")
        self.assertEqual(fields[1]["title"], "Направление")
        client.call.assert_awaited_once_with("crm.item.fields", {"entityTypeId": 2})


class AppSettingsTests(unittest.TestCase):
    def test_billing_start_date_is_a_separate_optional_setting(self):
        payload = AppSettingsPayload(
            field_planned_subscription_date="ufCrm_100",
            field_billing_start_date="ufCrm_200",
        )

        self.assertEqual(payload.field_planned_subscription_date, "ufCrm_100")
        self.assertEqual(payload.field_billing_start_date, "ufCrm_200")
