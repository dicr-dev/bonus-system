import unittest
from types import SimpleNamespace
from uuid import uuid4

from cr_portal.services.distribution import distribution_candidates


def user(name, *, department="Отдел внедрения", active=True):
    return SimpleNamespace(id=uuid4(), bitrix_id=1, full_name=name, department_name=department, is_active=active)


def deal(*, funnel="implementation", status="in_progress", owner=None, company=None, integration=False):
    return SimpleNamespace(funnel=funnel, status=status, implementation_responsible_user_id=owner,
                           company_bitrix_id=company, integration_1c=integration, bitrix_id=1,
                           title="Сделка", opportunity=100, machines_count=2)


class DistributionTests(unittest.TestCase):
    def test_company_employee_has_priority_over_lower_load(self):
        owner, free = user("Иван"), user("Анна")
        result = distribution_candidates(deal(company=10), [deal(owner=owner.id, company=10), deal(owner=owner.id)], [owner, free])
        self.assertEqual(result[0]["user_id"], str(owner.id))

    def test_integration_deal_uses_integration_load(self):
        few_integrations, many_integrations = user("Анна"), user("Иван")
        rows = [deal(owner=few_integrations.id) for _ in range(3)] + [deal(owner=many_integrations.id, integration=True)]
        result = distribution_candidates(deal(integration=True), rows, [few_integrations, many_integrations])
        self.assertEqual(result[0]["user_id"], str(few_integrations.id))

    def test_regular_deal_counts_only_tech_and_implementation_workload(self):
        tech_only, cr_start_only = user("Анна"), user("Иван")
        result = distribution_candidates(deal(), [deal(owner=tech_only.id), deal(funnel="cr_start", owner=cr_start_only.id), deal(funnel="cr_start", owner=cr_start_only.id)], [tech_only, cr_start_only])
        self.assertEqual(result[0]["user_id"], str(cr_start_only.id))
        self.assertEqual(result[0]["active_deals"], 0)
