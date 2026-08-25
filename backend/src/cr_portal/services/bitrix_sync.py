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
    except ValueError:
        return None


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")

    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _int(value: Any) -> int:
    if value in (None, ""):
        return 0

    try:
        return int(float(value))
    except Exception:
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value in (None, ""):
        return False

    return str(value).strip().upper() in {
        "Y",
        "YES",
        "TRUE",
        "1",
    }


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

    for stage in response.get("result", []):
        stage_id = str(stage.get("STATUS_ID") or "")

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

    for item in items:
        full_name = " ".join(
            value
            for value in [
                item.get("NAME"),
                item.get("LAST_NAME"),
            ]
            if value
        ).strip()

        if not full_name:
            full_name = f"Bitrix user {item['ID']}"

        await repo.upsert(
            bitrix_id=int(item["ID"]),
            email=item.get("EMAIL"),
            full_name=full_name,
            position=item.get("WORK_POSITION"),
        )

    await session.commit()

    return len(items)


async def sync_deals(
    session: AsyncSession,
    client: BitrixClient,
) -> int:
    configured_funnels = funnels()

    deal_repo = DealRepository(session)
    user_repo = UserRepository(session)

    total = 0

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

    custom_fields = [
        settings.BITRIX_FIELD_MONTHLY_AMOUNT,
        settings.BITRIX_FIELD_MACHINES_COUNT,
        settings.BITRIX_FIELD_INTEGRATION_1C,
        settings.BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID,
    ]

    for field_name in custom_fields:
        if field_name:
            select_fields.append(field_name)

    for category_id, funnel in configured_funnels.items():
        stage_semantics = await get_stage_semantics(
            client,
            category_id,
        )

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
            bitrix_id = int(item["id"])

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
            deal.title = str(
                item.get("title") or ""
            )

            deal.opportunity = _decimal(
                item.get("opportunity")
            )

            assigned_by_id = _int(
                item.get("assignedById")
            )

            deal.bitrix_assigned_by_id = (
                assigned_by_id or None
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

            if settings.BITRIX_FIELD_MONTHLY_AMOUNT:
                deal.monthly_amount = _decimal(
                    item.get(
                        settings.BITRIX_FIELD_MONTHLY_AMOUNT
                    )
                )

            if settings.BITRIX_FIELD_MACHINES_COUNT:
                deal.machines_count = _int(
                    item.get(
                        settings.BITRIX_FIELD_MACHINES_COUNT
                    )
                )

            if settings.BITRIX_FIELD_INTEGRATION_1C:
                deal.integration_1c = _bool(
                    item.get(
                        settings.BITRIX_FIELD_INTEGRATION_1C
                    )
                )

            if (
                settings
                .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
            ):
                implementation_bitrix_id = _int(
                    item.get(
                        settings
                        .BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID
                    )
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

            deal.created_time = _parse_datetime(
                item.get("createdTime")
            )

            deal.closed_time = _parse_datetime(
                item.get("closedTime")
            )

            deal.raw_json = json.dumps(
                item,
                ensure_ascii=False,
                default=str,
            )

            total += 1

    await session.commit()

    return total