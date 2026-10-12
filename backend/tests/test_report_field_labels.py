import json
import unittest
from types import SimpleNamespace

from cr_portal.services.report_builder import refresh_report_fields


class Result:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self.values


class FieldLabelsTest(unittest.IsolatedAsyncioTestCase):
    async def test_existing_labels_are_updated_without_changing_codes_or_enabled_flags(self):
        deal_field = SimpleNamespace(entity_type="deals", code="raw.ufCrm_123", title="ufCrm_123", field_type="string", is_enabled=True)
        task_field = SimpleNamespace(entity_type="tasks", code="raw.responsibleId", title="responsibleId", field_type="string", is_enabled=False)

        class Session:
            def __init__(self):
                self.results = iter([
                    [json.dumps({"ufCrm_123": "x"})],
                    [json.dumps({"responsibleId": "42"})],
                    [deal_field, task_field],
                ])
                self.added = []

            async def execute(self, query):
                return Result(next(self.results))

            def add(self, field):
                self.added.append(field)

            async def commit(self):
                pass

        class Client:
            async def call(self, method, params):
                if method == "crm.item.fields":
                    return {"result": {"fields": {"ufCrm_123": {"title": "Ответственный за внедрение", "type": "employee"}}}}
                return {"result": {"fields": {"RESPONSIBLE_ID": {"title": "Исполнитель", "type": "integer"}}}}

        await refresh_report_fields(Session(), Client())
        self.assertEqual(deal_field.title, "Ответственный за внедрение")
        self.assertEqual(deal_field.code, "raw.ufCrm_123")
        self.assertTrue(deal_field.is_enabled)
        self.assertEqual(task_field.title, "Исполнитель")
        self.assertEqual(task_field.field_type, "integer")
        self.assertFalse(task_field.is_enabled)
