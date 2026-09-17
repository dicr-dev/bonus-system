import json
import re
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.models.user import User


def _raw(deal: Deal) -> dict:
    try:
        return json.loads(deal.raw_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def company_id(deal: Deal) -> int | None:
    if deal.company_bitrix_id:
        return deal.company_bitrix_id
    value = _raw(deal).get("companyId")
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def normalized_title(value: str) -> str:
    value = re.sub(r"^\s*(?:№|#)?\s*\d+\s*[-—:.]?\s*", "", value or "")
    return re.sub(r"\s+", " ", value).strip().casefold()


def months_between(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None or end < start:
        return None
    return max(0, (end.year - start.year) * 12 + end.month - start.month - (end.day < start.day))


def _deal_row(deal: Deal | None, managers: dict) -> dict | None:
    if deal is None:
        return None
    return {
        "id": str(deal.id), "bitrix_id": deal.bitrix_id, "title": deal.title,
        "status": deal.status, "stage_title": deal.stage_title,
        "created_time": deal.created_time, "closed_time": deal.closed_time,
        "manager_name": managers.get(deal.implementation_responsible_user_id),
    }


async def deal_groups_report(session: AsyncSession, billing_start_field: str) -> dict:
    deals = list((await session.execute(select(Deal).where(Deal.funnel.in_(("tech_integration", "implementation", "support"))))).scalars())
    users = {user.id: user.full_name for user in (await session.execute(select(User))).scalars()}
    tech = {deal.bitrix_id: deal for deal in deals if deal.funnel == "tech_integration"}
    implementations = [deal for deal in deals if deal.funnel == "implementation"]
    supports = [deal for deal in deals if deal.funnel == "support"]
    implementations_by_parent: dict[int, list[Deal]] = defaultdict(list)
    supports_by_parent: dict[int, list[Deal]] = defaultdict(list)
    for deal in implementations:
        if deal.source_deal_bitrix_id:
            implementations_by_parent[deal.source_deal_bitrix_id].append(deal)
    for deal in supports:
        if deal.source_deal_bitrix_id:
            supports_by_parent[deal.source_deal_bitrix_id].append(deal)
    tech_candidates: dict[tuple[int | None, str | None, str], list[Deal]] = defaultdict(list)
    implementation_candidates: dict[tuple[int | None, str | None, str], list[Deal]] = defaultdict(list)
    tech_by_company_module: dict[tuple[int | None, str | None], list[Deal]] = defaultdict(list)
    implementation_by_company_module: dict[tuple[int | None, str | None], list[Deal]] = defaultdict(list)
    for deal in tech.values():
        tech_candidates[(company_id(deal), deal.module_name, normalized_title(deal.title))].append(deal)
        tech_by_company_module[(company_id(deal), deal.module_name)].append(deal)
    for deal in implementations:
        implementation_candidates[(company_id(deal), deal.module_name, normalized_title(deal.title))].append(deal)
        implementation_by_company_module[(company_id(deal), deal.module_name)].append(deal)

    rows: list[dict] = []
    issues: list[dict] = []
    used_implementations: set[int] = set()
    used_supports: set[int] = set()

    def make_row(tech_deal: Deal | None, implementation: Deal | None, support: Deal | None) -> dict:
        anchor = tech_deal or implementation or support
        support_raw = _raw(support) if support else {}
        billing = support_raw.get(billing_start_field) if billing_start_field else None
        try:
            billing_date = datetime.fromisoformat(str(billing).replace("Z", "+00:00")) if billing else None
            if billing_date and billing_date.tzinfo is None:
                billing_date = billing_date.replace(tzinfo=UTC)
        except ValueError:
            billing_date = None
        subscription_end = support.closed_time if support and support.status != "in_progress" else datetime.now(UTC)
        return {
            "key": f"{tech_deal.bitrix_id if tech_deal else 0}:{implementation.bitrix_id if implementation else 0}:{support.bitrix_id if support else 0}",
            "company_id": company_id(anchor), "company_name": anchor.company_name or (f"Организация #{company_id(anchor)}" if company_id(anchor) else "Без организации"),
            "module_name": anchor.module_name, "client_status": "Работает" if support and support.status == "in_progress" else "Не пользуется" if support else "Нет сделки Сопровождения",
            "tech": _deal_row(tech_deal, users), "implementation": _deal_row(implementation, users), "support": _deal_row(support, users),
            "tech_months": months_between(tech_deal.created_time, tech_deal.closed_time) if tech_deal else None,
            "implementation_months": months_between(implementation.created_time, implementation.closed_time) if implementation else None,
            "subscription_months": months_between(billing_date, subscription_end),
        }

    for tech_deal in tech.values():
        linked = implementations_by_parent.get(tech_deal.bitrix_id, [])
        if len(linked) != 1:
            rows.append(make_row(tech_deal, None, None))
            if len(linked) > 1:
                for item in linked:
                    key = (company_id(item), item.module_name, normalized_title(item.title))
                    issues.append({"type": "multiple_implementations", "title": "У Техинтеграции несколько сделок Внедрения", "child_deals": [_deal_row(item, users)], "parent": _deal_row(tech_deal, users), "candidates": [_deal_row(candidate, users) for candidate in tech_by_company_module.get(key[:2], [])]})
            continue
        implementation = linked[0]
        used_implementations.add(implementation.bitrix_id)
        linked_supports = supports_by_parent.get(implementation.bitrix_id, [])
        if len(linked_supports) == 1:
            support = linked_supports[0]
            used_supports.add(support.bitrix_id)
            rows.append(make_row(tech_deal, implementation, support))
        else:
            rows.append(make_row(tech_deal, implementation, None))
            if len(linked_supports) > 1:
                for item in linked_supports:
                    key = (company_id(item), item.module_name, normalized_title(item.title))
                    issues.append({"type": "multiple_supports", "title": "У Внедрения несколько сделок Сопровождения", "child_deals": [_deal_row(item, users)], "parent": _deal_row(implementation, users), "candidates": [_deal_row(candidate, users) for candidate in implementation_by_company_module.get(key[:2], [])]})

    for implementation in implementations:
        if implementation.bitrix_id in used_implementations:
            continue
        linked_supports = supports_by_parent.get(implementation.bitrix_id, [])
        support = linked_supports[0] if len(linked_supports) == 1 else None
        if support:
            used_supports.add(support.bitrix_id)
        rows.append(make_row(None, implementation, support))
        if not implementation.source_deal_bitrix_id or implementation.source_deal_bitrix_id not in tech:
            key = (company_id(implementation), implementation.module_name, normalized_title(implementation.title))
            issues.append({"type": "implementation_without_tech", "title": "Внедрение без корректной ссылки на Техинтеграцию", "child_deals": [_deal_row(implementation, users)], "parent": None, "candidates": [_deal_row(candidate, users) for candidate in tech_by_company_module.get(key[:2], [])]})
    for support in supports:
        if support.bitrix_id in used_supports:
            continue
        key = (company_id(support), support.module_name, normalized_title(support.title))
        exact_candidates = implementation_candidates.get(key, [])
        candidates = exact_candidates or implementation_by_company_module.get(key[:2], [])
        issues.append({"type": "support_without_implementation", "title": "Сопровождение без ссылки на Внедрение", "child_deals": [_deal_row(support, users)], "parent": None, "candidates": [_deal_row(item, users) for item in candidates], "auto_candidate": _deal_row(exact_candidates[0], users) if len(exact_candidates) == 1 else None})
        rows.append(make_row(None, None, support))
    return {"groups": rows, "issues": issues}
