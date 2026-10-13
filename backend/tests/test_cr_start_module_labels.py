import json
import unittest
from types import SimpleNamespace

from cr_portal.services.bonus import cr_start_counts_as_implementation


class CrStartModuleLabelsTests(unittest.TestCase):
    def setUp(self):
        self.business = SimpleNamespace(field_module="UF_MODULE", cr_start_implementation_modules=["КР Старт ТМ", "КР Старт Эксплуатация"])

    def test_normalized_label_resolves_numeric_bitrix_enum(self):
        deal = SimpleNamespace(module_name="КР Старт ТМ", raw_json=json.dumps({"UF_MODULE": 737}))
        self.assertTrue(cr_start_counts_as_implementation(deal, self.business))

    def test_normalized_label_is_case_insensitive(self):
        deal = SimpleNamespace(module_name="  кр старт эксплуатация ", raw_json=json.dumps({"UF_MODULE": 738}))
        self.assertTrue(cr_start_counts_as_implementation(deal, self.business))

    def test_other_module_is_not_implementation(self):
        deal = SimpleNamespace(module_name="Логистика", raw_json=json.dumps({"UF_MODULE": 123}))
        self.assertFalse(cr_start_counts_as_implementation(deal, self.business))

    def test_legacy_label_snapshot_still_supported(self):
        deal = SimpleNamespace(raw_json=json.dumps({"UF_MODULE": "КР Старт ТМ"}))
        self.assertTrue(cr_start_counts_as_implementation(deal, self.business))

    def test_numeric_id_without_resolved_label_is_not_guessed(self):
        deal = SimpleNamespace(module_name=None, raw_json=json.dumps({"UF_MODULE": 737}))
        self.assertFalse(cr_start_counts_as_implementation(deal, self.business))


if __name__ == "__main__":
    unittest.main()
