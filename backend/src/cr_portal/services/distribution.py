from collections import Counter

from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.services.employee_scope import employee_is_in_department


ASSIGNABLE_FUNNELS = frozenset({"tech_integration", "implementation"})


def distribution_candidates(deal: Deal, deals: list[Deal], users: list[User], *, roster_ids: set | None = None) -> list[dict]:
    """Rank implementation employees for a new Tech Integration/Implementation deal."""
    if deal.funnel not in ASSIGNABLE_FUNNELS:
        raise ValueError("Помощник доступен только для сделок Техинтеграции и Внедрения")

    employees = [user for user in users if user.is_active and employee_is_in_department(user, "Отдел внедрения")
                 and (not roster_ids or user.id in roster_ids)]
    active = [item for item in deals if item.status == "in_progress"]
    workload = Counter(item.implementation_responsible_user_id for item in active
                       if item.funnel in ASSIGNABLE_FUNNELS and item.implementation_responsible_user_id)
    integration_workload = Counter(item.implementation_responsible_user_id for item in active
                                   if item.funnel in ASSIGNABLE_FUNNELS and item.integration_1c
                                   and item.implementation_responsible_user_id)
    company_workload = Counter(item.implementation_responsible_user_id for item in active
                               if deal.company_bitrix_id is not None and item.company_bitrix_id == deal.company_bitrix_id
                               and item.implementation_responsible_user_id)

    def sort_key(user: User):
        company_count = company_workload[user.id]
        primary_load = integration_workload[user.id] if deal.integration_1c else workload[user.id]
        return (-company_count, primary_load, workload[user.id], user.full_name.casefold())

    result = []
    for user in sorted(employees, key=sort_key):
        employee_deals = [item for item in active if item.funnel in ASSIGNABLE_FUNNELS and item.implementation_responsible_user_id == user.id]
        company_count, active_count, integrations_count = (company_workload[user.id], workload[user.id], integration_workload[user.id])
        reason = (f"Уже ведёт {company_count} активн. сделок этой компании" if company_count else
                  f"Активных сделок с интеграцией: {integrations_count}" if deal.integration_1c else
                  f"Активных сделок: {active_count}")
        result.append({"user_id": str(user.id), "bitrix_id": user.bitrix_id, "full_name": user.full_name,
                       "company_active_deals": company_count, "active_deals": active_count,
                       "active_integration_deals": integrations_count, "reason": reason,
                       "deals": [{"bitrix_id": item.bitrix_id, "title": item.title, "funnel": item.funnel,
                                  "amount": str(item.opportunity or 0), "machines_count": item.machines_count or 0,
                                  "integration_1c": item.integration_1c} for item in employee_deals]})
    return result
