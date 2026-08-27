import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.core.config import settings
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.deal import Deal
from cr_portal.repositories.deals import DealRepository
from cr_portal.repositories.users import UserRepository
from cr_portal.services.kpi import ensure_kpi_event


STATUS_MAP = {
    "process": "in_progress",
    "success": "won",
    "failure": "lost",
    "apology": "lost",
}

# Поле Bitrix24 «Направление (Модуль)».
BITRIX_MODULE_FIELD = "ufCrm_1650618044049"

ProgressCallback = Callable[
    [str, int, int],
    Awaitable[None],
]


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
        int(category_id): name
        for category_id, name in pairs
        if category_id is not None
    }


def _dt(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except Exception:
        return None


def _dec(value: Any) -> Decimal:
    if value in (
        None,
        "",
    ):
        return Decimal("0")

    if (
        isinstance(value, str)
        and "|" in value
    ):
        value = value.split(
            "|",
            1,
        )[0]

    try:
        return Decimal(
            str(value)
        )
    except Exception:
        return Decimal("0")


def _int(value: Any) -> int:
    if value in (
        None,
        "",
    ):
        return 0

    if isinstance(
        value,
        list,
    ):
        value = (
            value[0]
            if value
            else 0
        )

    # CRM-поле Bitrix может вернуть D_12345.
    if isinstance(
        value,
        str,
    ):
        raw = value.strip()

        if raw.upper().startswith(
            "D_"
        ):
            raw = raw[2:]

        value = raw

    try:
        return int(
            float(value)
        )
    except Exception:
        return 0


def _bool(value: Any) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    raw = str(
        value or ""
    ).strip()

    # Для поля «!Интеграция 1С»
    # ранее были определены enum:
    # 199 = Да
    # 200 = Нет
    if raw == "199":
        return True

    if raw == "200":
        return False

    return (
        raw.upper()
        in {
            "Y",
            "YES",
            "TRUE",
            "1",
            "ДА",
        }
    )


async def get_stage_semantics(
    client: BitrixClient,
    category_id: int,
) -> dict[str, str]:
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

    for stage in response.get(
        "result",
        [],
    ):
        stage_id = str(
            stage.get(
                "STATUS_ID"
            )
            or ""
        )

        semantics = str(
            (
                stage.get(
                    "EXTRA"
                )
                or {}
            ).get(
                "SEMANTICS"
            )
            or ""
        ).lower()

        if stage_id:
            result[
                stage_id
            ] = semantics

    return result


async def sync_users(
    session: AsyncSession,
    client: BitrixClient,
) -> int:
    items = await client.call_all(
        "user.get",
        {},
    )

    repository = UserRepository(
        session
    )

    count = 0

    for item in items:
        raw_id = (
            item.get("ID")
            or item.get("id")
        )

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
            full_name = (
                f"Bitrix user {raw_id}"
            )

        user = await repository.upsert(
            int(raw_id),
            (
                item.get("EMAIL")
                or item.get("email")
            ),
            full_name,
            (
                item.get(
                    "WORK_POSITION"
                )
                or item.get(
                    "workPosition"
                )
            ),
        )

        active = (
            item.get("ACTIVE")
            if "ACTIVE" in item
            else item.get(
                "active"
            )
        )

        user.is_active = (
            active
            if isinstance(
                active,
                bool,
            )
            else (
                str(
                    active or ""
                )
                .strip()
                .upper()
                in {
                    "Y",
                    "YES",
                    "TRUE",
                    "1",
                }
            )
        )

        count += 1

    await session.commit()

    return count


async def sync_deals(
    session: AsyncSession,
    client: BitrixClient,
    *,
    updated_after: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> int:
    deal_repository = (
        DealRepository(
            session
        )
    )

    user_repository = (
        UserRepository(
            session
        )
    )

    total = 0
    funnel_map = funnels()

    #
    # ВАЖНО:
    # companyId и «Направление (Модуль)»
    # сохраняются в raw_json и используются
    # для отчета сопоставления Сопровождение → Внедрение.
    #
    select_fields = [
        "id",
        "title",
        "categoryId",
        "stageId",
        "assignedById",
        "companyId",
        "opportunity",
        "createdTime",
        "updatedTime",
        "movedTime",
        BITRIX_MODULE_FIELD,
    ]

    custom_fields = [
        settings.BITRIX_FIELD_MONTHLY_AMOUNT,
        settings.BITRIX_FIELD_MACHINES_COUNT,
        settings.BITRIX_FIELD_INTEGRATION_1C,
        settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID,
        settings.BITRIX_FIELD_SOURCE_DEAL_ID,
        settings.BITRIX_FIELD_SALES_BONUS_USER_ID,
        *settings.cr_start_boolean_fields,
    ]

    for field_name in (
        custom_fields
    ):
        if (
            field_name
            and field_name
            not in select_fields
        ):
            select_fields.append(
                field_name
            )

    funnel_items = list(
        funnel_map.items()
    )

    for index, (
        category_id,
        funnel_name,
    ) in enumerate(
        funnel_items
    ):
        semantics = (
            await get_stage_semantics(
                client,
                category_id,
            )
        )

        filter_data: dict[
            str,
            Any,
        ] = {
            "categoryId":
                category_id,
        }

        if updated_after:
            filter_data[
                ">=updatedTime"
            ] = updated_after

        items = await client.call_all(
            "crm.item.list",
            {
                "entityTypeId": 2,
                "select":
                    select_fields,
                "filter":
                    filter_data,
            },
        )

        for item in items:
            raw_id = item.get(
                "id"
            )

            if raw_id is None:
                continue

            bitrix_id = int(
                raw_id
            )

            deal = (
                await deal_repository
                .by_bitrix_id(
                    bitrix_id
                )
            )

            if deal is None:
                deal = Deal(
                    bitrix_id=bitrix_id,
                    category_id=(
                        category_id
                    ),
                    funnel=(
                        funnel_name
                    ),
                    stage_id="",
                    status=(
                        "in_progress"
                    ),
                    title="",
                )

                session.add(
                    deal
                )

            stage_id = str(
                item.get(
                    "stageId"
                )
                or ""
            )

            deal.status = (
                STATUS_MAP.get(
                    semantics.get(
                        stage_id,
                        "",
                    ),
                    "in_progress",
                )
            )

            deal.category_id = (
                category_id
            )

            deal.funnel = (
                funnel_name
            )

            deal.stage_id = (
                stage_id
            )

            deal.title = str(
                item.get(
                    "title"
                )
                or ""
            )

            deal.opportunity = (
                _dec(
                    item.get(
                        "opportunity"
                    )
                )
            )

            assigned_by_id = (
                _int(
                    item.get(
                        "assignedById"
                    )
                )
            )

            deal.bitrix_assigned_by_id = (
                assigned_by_id
                or None
            )

            assigned_user = (
                await user_repository
                .by_bitrix_id(
                    assigned_by_id
                )
                if assigned_by_id
                else None
            )

            deal.responsible_user_id = (
                assigned_user.id
                if assigned_user
                else None
            )

            if (
                settings
                .BITRIX_FIELD_MONTHLY_AMOUNT
            ):
                deal.monthly_amount = (
                    _dec(
                        item.get(
                            settings
                            .BITRIX_FIELD_MONTHLY_AMOUNT
                        )
                    )
                )

            if (
                settings
                .BITRIX_FIELD_MACHINES_COUNT
            ):
                deal.machines_count = (
                    _int(
                        item.get(
                            settings
                            .BITRIX_FIELD_MACHINES_COUNT
                        )
                    )
                )

            if (
                settings
                .BITRIX_FIELD_INTEGRATION_1C
            ):
                deal.integration_1c = (
                    _bool(
                        item.get(
                            settings
                            .BITRIX_FIELD_INTEGRATION_1C
                        )
                    )
                )

            #
            # Ответственный за внедрение.
            #
            deal.implementation_responsible_user_id = (
                None
            )

            if (
                settings
                .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
            ):
                implementation_user_bitrix_id = (
                    _int(
                        item.get(
                            settings
                            .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
                        )
                    )
                )

                implementation_user = (
                    await user_repository
                    .by_bitrix_id(
                        implementation_user_bitrix_id
                    )
                    if implementation_user_bitrix_id
                    else None
                )

                deal.implementation_responsible_user_id = (
                    implementation_user.id
                    if implementation_user
                    else None
                )

            #
            # Сотрудник, получающий бонус за продажу.
            #
            deal.sales_bonus_user_id = (
                None
            )

            if (
                settings
                .BITRIX_FIELD_SALES_BONUS_USER_ID
            ):
                sales_user_bitrix_id = (
                    _int(
                        item.get(
                            settings
                            .BITRIX_FIELD_SALES_BONUS_USER_ID
                        )
                    )
                )

                sales_user = (
                    await user_repository
                    .by_bitrix_id(
                        sales_user_bitrix_id
                    )
                    if sales_user_bitrix_id
                    else None
                )

                deal.sales_bonus_user_id = (
                    sales_user.id
                    if sales_user
                    else None
                )

            #
            # Для обратной совместимости сохраняем
            # первый ID из CRM-поля в отдельную колонку.
            #
            # Полный список связей остается в raw_json
            # и используется bonus.py.
            #
            if (
                settings
                .BITRIX_FIELD_SOURCE_DEAL_ID
            ):
                deal.source_deal_bitrix_id = (
                    _int(
                        item.get(
                            settings
                            .BITRIX_FIELD_SOURCE_DEAL_ID
                        )
                    )
                    or None
                )

            deal.created_time = (
                _dt(
                    item.get(
                        "createdTime"
                    )
                )
            )

            deal.updated_time = (
                _dt(
                    item.get(
                        "updatedTime"
                    )
                )
            )

            #
            # Universal API для сделок не возвращает closedTime.
            # Для закрытых сделок используем movedTime — время
            # последнего перехода стадии. Для won/lost это момент
            # перехода в финальную стадию.
            #
            moved_time = _dt(
                item.get(
                    "movedTime"
                )
            )

            deal.closed_time = (
                moved_time
                if deal.status in {
                    "won",
                    "lost",
                }
                else None
            )

            #
            # Здесь теперь гарантированно сохраняются:
            #
            # companyId
            # ufCrm_1650618044049 = Направление (Модуль)
            # ufCrm_1756883832 = ID сделки-источника
            # и остальные выбранные поля.
            #
            deal.raw_json = (
                json.dumps(
                    item,
                    ensure_ascii=False,
                    default=str,
                )
            )

            await session.flush()

            await ensure_kpi_event(
                session,
                deal,
            )

            total += 1

        await session.commit()

        if progress_callback:
            await progress_callback(
                funnel_name,
                total,
                int(
                    (
                        index
                        + 1
                    )
                    / len(
                        funnel_items
                    )
                    * 100
                ),
            )

    return total
