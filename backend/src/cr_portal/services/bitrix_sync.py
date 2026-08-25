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


STATUS_MAP = {
    "process": "in_progress",
    "success": "success",
    "failure": "failed",
    "apology": "failed",
}


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
        int(category_id): funnel
        for category_id, funnel in pairs
        if category_id is not None
    }


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _decimal(
    value: Any,
) -> Decimal:
    if value in (
        None,
        "",
    ):
        return Decimal("0")

    #
    # Bitrix money field:
    # 15600|RUB
    #
    if (
        isinstance(
            value,
            str,
        )
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
    except (
        TypeError,
        ValueError,
    ):
        return Decimal("0")


def _int(
    value: Any,
) -> int:
    if value in (
        None,
        "",
    ):
        return 0

    if isinstance(
        value,
        list,
    ):
        if not value:
            return 0

        value = value[0]

    try:
        return int(
            float(value)
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _bool(
    value: Any,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    if value in (
        None,
        "",
    ):
        return False

    value_str = str(
        value
    ).strip()

    #
    # Bitrix field:
    # !Интеграция 1С
    #
    # 199 = Да
    # 200 = Нет
    #
    if value_str == "199":
        return True

    if value_str == "200":
        return False

    return (
        value_str.upper()
        in {
            "Y",
            "YES",
            "TRUE",
            "1",
            "ДА",
        }
    )


def _active(
    value: Any,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    if value in (
        None,
        "",
    ):
        return False

    return (
        str(value)
        .strip()
        .upper()
        in {
            "Y",
            "YES",
            "TRUE",
            "1",
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

    result: dict[
        str,
        str,
    ] = {}

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

        extra = (
            stage.get(
                "EXTRA"
            )
            or {}
        )

        semantics = str(
            extra.get(
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
    #
    # ВАЖНО:
    # call_all() забирает все страницы.
    #
    # user.get возвращает максимум
    # ограниченное число пользователей
    # за один запрос.
    #
    # FILTER ACTIVE здесь специально
    # НЕ используем.
    #
    items = await client.call_all(
        "user.get",
        {},
    )

    repo = UserRepository(
        session
    )

    synced = 0

    for item in items:
        raw_id = (
            item.get(
                "ID"
            )
            or item.get(
                "id"
            )
        )

        if raw_id is None:
            continue

        first_name = (
            item.get(
                "NAME"
            )
            or item.get(
                "name"
            )
        )

        last_name = (
            item.get(
                "LAST_NAME"
            )
            or item.get(
                "lastName"
            )
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

        active_value = (
            item.get(
                "ACTIVE"
            )
            if "ACTIVE" in item
            else item.get(
                "active"
            )
        )

        user = await repo.upsert(
            bitrix_id=int(
                raw_id
            ),
            email=(
                item.get(
                    "EMAIL"
                )
                or item.get(
                    "email"
                )
            ),
            full_name=full_name,
            position=(
                item.get(
                    "WORK_POSITION"
                )
                or item.get(
                    "workPosition"
                )
            ),
        )

        user.is_active = (
            _active(
                active_value
            )
        )

        synced += 1

    await session.commit()

    return synced


async def sync_deals(
    session: AsyncSession,
    client: BitrixClient,
    *,
    updated_after: str | None = None,
    progress_callback:
        ProgressCallback | None = None,
) -> int:
    configured_funnels = (
        funnels()
    )

    deal_repo = (
        DealRepository(
            session
        )
    )

    user_repo = (
        UserRepository(
            session
        )
    )

    total = 0

    #
    # Universal API system fields
    #
    select_fields = [
        "id",
        "title",
        "categoryId",
        "stageId",
        "assignedById",
        "opportunity",
        "createdTime",
        "updatedTime",
        "closedTime",
    ]

    #
    # Custom Bitrix fields.
    #
    # В .env должны быть:
    #
    # BITRIX_FIELD_MONTHLY_AMOUNT
    # BITRIX_FIELD_MACHINES_COUNT
    # BITRIX_FIELD_INTEGRATION_1C
    # BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
    #
    custom_fields = [
        settings
        .BITRIX_FIELD_MONTHLY_AMOUNT,

        settings
        .BITRIX_FIELD_MACHINES_COUNT,

        settings
        .BITRIX_FIELD_INTEGRATION_1C,

        settings
        .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID,
    ]

    for field_name in custom_fields:
        if (
            field_name
            and field_name
            not in select_fields
        ):
            select_fields.append(
                field_name
            )

    funnel_items = list(
        configured_funnels.items()
    )

    funnel_count = len(
        funnel_items
    )

    for funnel_index, (
        category_id,
        funnel,
    ) in enumerate(
        funnel_items
    ):
        #
        # Стадии и semantics
        #
        stage_semantics = (
            await get_stage_semantics(
                client,
                category_id,
            )
        )

        deal_filter: dict[
            str,
            Any,
        ] = {
            "categoryId":
                category_id,
        }

        #
        # Инкрементальная
        # синхронизация.
        #
        if updated_after:
            deal_filter[
                ">=updatedTime"
            ] = updated_after

        #
        # Все страницы сделок
        # данной воронки.
        #
        items = (
            await client.call_all(
                "crm.item.list",
                {
                    "entityTypeId":
                        2,

                    "select":
                        select_fields,

                    "filter":
                        deal_filter,
                },
            )
        )

        for item in items:
            raw_bitrix_id = (
                item.get(
                    "id"
                )
            )

            if raw_bitrix_id is None:
                continue

            bitrix_id = int(
                raw_bitrix_id
            )

            deal = (
                await deal_repo
                .by_bitrix_id(
                    bitrix_id
                )
            )

            if deal is None:
                deal = Deal(
                    bitrix_id=
                        bitrix_id,

                    category_id=
                        category_id,

                    funnel=
                        funnel,

                    stage_id=
                        "",

                    status=
                        "in_progress",

                    title=
                        "",
                )

                session.add(
                    deal
                )

            #
            # Stage
            #
            stage_id = str(
                item.get(
                    "stageId"
                )
                or ""
            )

            semantics = (
                stage_semantics.get(
                    stage_id,
                    "",
                )
            )

            deal.status = (
                STATUS_MAP.get(
                    semantics,
                    "in_progress",
                )
            )

            deal.category_id = (
                category_id
            )

            deal.funnel = (
                funnel
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
                _decimal(
                    item.get(
                        "opportunity"
                    )
                )
            )

            #
            # Стандартный
            # Ответственный Bitrix24.
            #
            assigned_by_id = (
                _int(
                    item.get(
                        "assignedById"
                    )
                )
            )

            deal.bitrix_assigned_by_id = (
                assigned_by_id
                if assigned_by_id
                else None
            )

            assigned_user = None

            if assigned_by_id:
                assigned_user = (
                    await user_repo
                    .by_bitrix_id(
                        assigned_by_id
                    )
                )

            deal.responsible_user_id = (
                assigned_user.id
                if assigned_user
                else None
            )

            #
            # Сумма оплаты в месяц
            #
            if (
                settings
                .BITRIX_FIELD_MONTHLY_AMOUNT
            ):
                deal.monthly_amount = (
                    _decimal(
                        item.get(
                            settings
                            .BITRIX_FIELD_MONTHLY_AMOUNT
                        )
                    )
                )

            #
            # Количество машин
            #
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

            #
            # Интеграция 1С
            #
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
            # Ответственный
            # за внедрение.
            #
            # Сначала очищаем,
            # чтобы удалённое значение
            # в Bitrix тоже
            # корректно удалилось
            # у нас.
            #
            deal.implementation_responsible_user_id = (
                None
            )

            if (
                settings
                .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
            ):
                implementation_value = (
                    item.get(
                        settings
                        .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
                    )
                )

                implementation_bitrix_id = (
                    _int(
                        implementation_value
                    )
                )

                if (
                    implementation_bitrix_id
                ):
                    implementation_user = (
                        await user_repo
                        .by_bitrix_id(
                            implementation_bitrix_id
                        )
                    )

                    if implementation_user:
                        deal.implementation_responsible_user_id = (
                            implementation_user.id
                        )

            #
            # Dates
            #
            deal.created_time = (
                _parse_datetime(
                    item.get(
                        "createdTime"
                    )
                )
            )

            deal.closed_time = (
                _parse_datetime(
                    item.get(
                        "closedTime"
                    )
                )
            )

            #
            # Raw Bitrix response
            #
            deal.raw_json = (
                json.dumps(
                    item,
                    ensure_ascii=False,
                    default=str,
                )
            )

            total += 1

        #
        # Commit после каждой
        # воронки.
        #
        await session.commit()

        progress = int(
            (
                (
                    funnel_index
                    + 1
                )
                / funnel_count
            )
            * 100
        )

        if progress_callback:
            await progress_callback(
                funnel,
                total,
                progress,
            )

    return total