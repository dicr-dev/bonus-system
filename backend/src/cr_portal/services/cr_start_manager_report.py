from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.models.user import User


WORKING_STAGES = frozenset({
    "Новая",
    "В работе",
    "На подключении мониторинга",
    "Есть ЛК / Мониторинг подключен",
    "Начали работать",
    "Исп-ют документы",
    "Прошел 14 дневный тест",
})
COMMERCIAL_STAGES = frozenset({
    "Коммерческое использование",
    "Неделя до продления подписки",
    "Период оплачен",
    "Партнерский ЛК",
})
LOST_STAGES = frozenset({
    "Дубль",
    "Нет навигации и не будут подключать",
    "Нет собственных ТС",
    "Некачественный лид",
    "Не понял ценность",
    "Слишком дорого",
    "Не тестировал/Нет времени",
    "Вернутся позже",
    "Нет ответа после теста",
    "Выбрали других",
    "1ТС",
    "Не целевой (городские, малотоннажки, самосвалы и прочее)",
    "Регался исполнитель, не достучались до ЛПР",
    "Перестали отвечать",
})


def _stage_group(stage_title: str | None) -> str | None:
    title = " ".join((stage_title or "").split())
    if title in WORKING_STAGES:
        return "working"
    if title in COMMERCIAL_STAGES:
        return "commercial"
    if title in LOST_STAGES:
        return "lost"
    return None


async def cr_start_manager_report(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Deal, User.id, User.full_name)
        .select_from(Deal)
        .outerjoin(User, Deal.implementation_responsible_user_id == User.id)
        .where(Deal.funnel == "cr_start")
        .order_by(User.full_name, Deal.title, Deal.bitrix_id)
    )

    groups: dict[str, dict] = {}
    for deal, user_id, user_name in result.all():
        group_name = _stage_group(deal.stage_title)
        if group_name is None:
            continue

        key = str(user_id) if user_id else "unassigned"
        group = groups.setdefault(
            key,
            {
                "implementation_responsible_id": key,
                "implementation_responsible_name": user_name or "Без ответственного за внедрение",
                "deals_count": 0,
                "opportunity": Decimal(0),
                "working_count": 0,
                "working_opportunity": Decimal(0),
                "commercial_count": 0,
                "commercial_opportunity": Decimal(0),
                "lost_count": 0,
                "lost_opportunity": Decimal(0),
                "deals": [],
            },
        )
        amount = deal.opportunity or Decimal(0)
        group["deals_count"] += 1
        group["opportunity"] += amount
        group[f"{group_name}_count"] += 1
        group[f"{group_name}_opportunity"] += amount
        group["deals"].append(
            {
                "id": str(deal.id),
                "bitrix_id": deal.bitrix_id,
                "title": deal.title,
                "stage_title": deal.stage_title or "—",
                "opportunity": str(amount),
            }
        )

    money_fields = (
        "opportunity",
        "working_opportunity",
        "commercial_opportunity",
        "lost_opportunity",
    )
    return [
        {
            **group,
            **{field: str(group[field]) for field in money_fields},
        }
        for group in sorted(
            groups.values(),
            key=lambda item: item["implementation_responsible_name"].casefold(),
        )
    ]
