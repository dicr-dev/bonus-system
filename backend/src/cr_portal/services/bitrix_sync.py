import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.core.config import settings
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.deal import Deal
from cr_portal.repositories.deals import DealRepository
from cr_portal.repositories.users import UserRepository


STATUS_MAP = {
    "process": "in_progress",
    "success": "success",
    "failure": "failed",
    "apology": "failed",
}


def funnels() -> dict[int, str]:
    pairs = [
        (
            settings.BITRIX_TECH_INTEGRATION_CATEGORY_ID,
            "tech_integration",
        ),
        (
            settings.BITRIX_IMPLEMENTATION_CATEGORY_ID,
            "implementation",
        ),
        (
            settings.BITRIX_CR_START_CATEGORY_ID,
            "cr_start",
        ),
        (
            settings.BITRIX_SUPPORT_CATEGORY_ID,
            "support",
        ),
    ]

    return {
        int(category_id): funnel
        for category_id, funnel in pairs
        if category_id is not None
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")

    # Поля типа money Bitrix24 могут приходить:
    # 15600|RUB
    if isinstance(value, str) and "|" in value:
        value = value.split("|", 1)[0]

    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return Decimal("0")


def _int(value: Any) -> int:
    if value in (None, ""):
        return 0

    if isinstance(value, list):
        if not value:
            return 0

        value = value[0]

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value in (None, ""):
        return False

    value_str = str(value).strip()

    if value_str == "199":
        return True

    if value_str == "200":
        return False

    return value_str.upper() in {
        "Y",
        "YES",
        "TRUE",
        "1",
        "ДА",
    }


async def get_stage_semantics(
    client: BitrixClient,
    category_id: int,
) -> dict[str, str]:
    """
    Получает стадии воронки Bitrix24 и их семантику.

    process  -> сделка в работе
    success  -> успешно закрыта
    failure  -> неуспешно закрыта
    apology  -> неуспешно закрыта
    """

    entity_id = (
        "DEAL_STAGE"
        if category_id == 0
        else f"DEAL_STAGE_{category_id}"
    )

    response = await client.call(
        "crm.status.list",
        {
            "filter": {
                "ENTITY_ID": entity_id,
            },
            "order": {
                "SORT": "ASC",
            },
        },
    )

    result: dict[str, str] = {}

    for stage in response.get("result", []):
        stage_id = str(
            stage.get("STATUS_ID") or ""
        )

        extra = stage.get("EXTRA") or {}

        semantics = str(
            extra.get("SEMANTICS") or ""
        ).lower()

        if stage_id:
            result[stage_id] = semantics

    return result


async def sync_users(
    session: AsyncSession,
    client: BitrixClient,
) -> int:
    response = await client.call(
        "user.get",
        {
            "FILTER": {
                "ACTIVE": True,
            },
        },
    )

    items = response.get("result", [])

    repo = UserRepository(session)

    synced = 0

    for item in items:
        raw_id = item.get("ID") or item.get("id")

        if raw_id is None:
            continue

        first_name = (
            item.get("NAME")
            or item.get("name")
        )

        last_name = (
            item.get("LAST_NAME")
            or item.get("lastName")
        )

        full_name = " ".join(
            str(value)
            for value in [
                first_name,
                last_name,
            ]
            if value
        ).strip()

        if not full_name:
            full_name = f"Bitrix user {raw_id}"

        await repo.upsert(
            bitrix_id=int(raw_id),
            email=(
                item.get("EMAIL")
                or item.get("email")
            ),
            full_name=full_name,
            position=(
                item.get("WORK_POSITION")
                or item.get("workPosition")
            ),
        )

        synced += 1

    await session.commit()

    return synced


async def sync_deals(
    session: AsyncSession,
    client: BitrixClient,
) -> int:
    configured_funnels = funnels()

    deal_repo = DealRepository(session)
    user_repo = UserRepository(session)

    total = 0

    #
    # Universal CRM API использует camelCase.
    #
    select_fields = [
        "id",
        "title",
        "categoryId",
        "stageId",
        "assignedById",
        "opportunity",
        "createdTime",
        "closedTime",
    ]

    #
    # Эти значения должны быть в backend/.env
    # тоже в camelCase:
    #
    # ufCrm_1727777946781
    # ufCrm_1709713841602
    # ufCrm_1779790857212
    # ufCrm_1642670939
    #
    custom_fields = [
        settings.BITRIX_FIELD_MONTHLY_AMOUNT,
        settings.BITRIX_FIELD_MACHINES_COUNT,
        settings.BITRIX_FIELD_INTEGRATION_1C,
        settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID,
    ]

    for field_name in custom_fields:
        if (
            field_name
            and field_name not in select_fields
        ):
            select_fields.append(field_name)

    for category_id, funnel in configured_funnels.items():
        #
        # Получаем семантику стадий конкретной воронки.
        #
        stage_semantics = await get_stage_semantics(
            client,
            category_id,
        )

        #
        # Получаем все сделки воронки.
        #
        items = await client.call_all(
            "crm.item.list",
            {
                "entityTypeId": 2,
                "select": select_fields,
                "filter": {
                    "categoryId": category_id,
                },
            },
        )

        for item in items:
            raw_bitrix_id = item.get("id")

            if raw_bitrix_id is None:
                continue

            bitrix_id = int(raw_bitrix_id)

            deal = await deal_repo.by_bitrix_id(
                bitrix_id
            )

            if deal is None:
                deal = Deal(
                    bitrix_id=bitrix_id,
                    category_id=category_id,
                    funnel=funnel,
                    stage_id="",
                    status="in_progress",
                    title="",
                )

                session.add(deal)

            #
            # Стадия и статус.
            #
            stage_id = str(
                item.get("stageId") or ""
            )

            semantics = stage_semantics.get(
                stage_id,
                "",
            )

            deal.status = STATUS_MAP.get(
                semantics,
                "in_progress",
            )

            deal.category_id = category_id
            deal.funnel = funnel
            deal.stage_id = stage_id

            #
            # Основные поля сделки.
            #
            deal.title = str(
                item.get("title") or ""
            )

            deal.opportunity = _decimal(
                item.get("opportunity")
            )

            #
            # Основной ответственный Bitrix24.
            #
            assigned_by_id = _int(
                item.get("assignedById")
            )

            deal.bitrix_assigned_by_id = (
                assigned_by_id
                if assigned_by_id
                else None
            )

            assigned_user = None

            if assigned_by_id:
                assigned_user = (
                    await user_repo.by_bitrix_id(
                        assigned_by_id
                    )
                )

            deal.responsible_user_id = (
                assigned_user.id
                if assigned_user
                else None
            )

            #
            # Сумма оплаты в месяц.
            #
            if settings.BITRIX_FIELD_MONTHLY_AMOUNT:
                deal.monthly_amount = _decimal(
                    item.get(
                        settings.BITRIX_FIELD_MONTHLY_AMOUNT
                    )
                )

            #
            # Количество машин.
            #
            if settings.BITRIX_FIELD_MACHINES_COUNT:
                deal.machines_count = _int(
                    item.get(
                        settings.BITRIX_FIELD_MACHINES_COUNT
                    )
                )

            #
            # Интеграция с 1С.
            #
            if settings.BITRIX_FIELD_INTEGRATION_1C:
                deal.integration_1c = _bool(
                    item.get(
                        settings.BITRIX_FIELD_INTEGRATION_1C
                    )
                )

            #
            # Ответственный за внедрение.
            #
            if (
                settings
                .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
            ):
                implementation_value = item.get(
                    settings
                    .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
                )

                implementation_bitrix_id = _int(
                    implementation_value
                )

                if implementation_bitrix_id:
                    implementation_user = (
                        await user_repo.by_bitrix_id(
                            implementation_bitrix_id
                        )
                    )

                    if implementation_user:
                        deal.responsible_user_id = (
                            implementation_user.id
                        )

            #
            # Даты.
            #
            deal.created_time = _parse_datetime(
                item.get("createdTime")
            )

            deal.closed_time = _parse_datetime(
                item.get("closedTime")
            )

            #
            # Сохраняем исходный ответ Bitrix24.
            #
            deal.raw_json = json.dumps(
                item,
                ensure_ascii=False,
                default=str,
            )

            total += 1

    await session.commit()

    return total