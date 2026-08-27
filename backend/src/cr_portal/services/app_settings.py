from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.core.config import settings
from cr_portal.models.app_settings import AppSetting


@dataclass(slots=True)
class BusinessSettings:
    tech_integration_category_id: int | None
    implementation_category_id: int | None
    cr_start_category_id: int | None
    support_category_id: int | None
    field_monthly_amount: str
    field_machines_count: str
    field_integration_1c: str
    field_implementation_responsible_id: str
    field_source_deal_id: str
    field_sales_bonus_user_id: str
    cr_start_boolean_fields: list[str]
    field_client_works: str
    task_training_bonus_field: str
    field_module: str
    field_integration_amount: str


KEYS = {
    "tech_integration_category_id": "BITRIX_TECH_INTEGRATION_CATEGORY_ID",
    "implementation_category_id": "BITRIX_IMPLEMENTATION_CATEGORY_ID",
    "cr_start_category_id": "BITRIX_CR_START_CATEGORY_ID",
    "support_category_id": "BITRIX_SUPPORT_CATEGORY_ID",
    "field_monthly_amount": "BITRIX_FIELD_MONTHLY_AMOUNT",
    "field_machines_count": "BITRIX_FIELD_MACHINES_COUNT",
    "field_integration_1c": "BITRIX_FIELD_INTEGRATION_1C",
    "field_implementation_responsible_id": "BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID",
    "field_source_deal_id": "BITRIX_FIELD_SOURCE_DEAL_ID",
    "field_sales_bonus_user_id": "BITRIX_FIELD_SALES_BONUS_USER_ID",
    "cr_start_boolean_fields": "BITRIX_CR_START_BOOLEAN_FIELDS",
    "field_client_works": "BITRIX_FIELD_CLIENT_WORKS",
    "task_training_bonus_field": "BITRIX_TASK_TRAINING_BONUS_FIELD",
    "field_module": "BITRIX_FIELD_MODULE",
    "field_integration_amount": "BITRIX_FIELD_INTEGRATION_AMOUNT",
}


def _env_default(name: str) -> str:
    if name == "BITRIX_FIELD_MODULE":
        return getattr(settings, name, "ufCrm_1650618044049") or ""
    return str(getattr(settings, name, "") or "")


def _to_int(value: str) -> int | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


async def ensure_app_settings(session: AsyncSession) -> dict[str, str]:
    rows = (await session.execute(select(AppSetting))).scalars().all()
    values = {row.key: row.value for row in rows}

    for _, env_name in KEYS.items():
        if env_name not in values:
            value = _env_default(env_name)
            session.add(AppSetting(key=env_name, value=value))
            values[env_name] = value

    await session.flush()
    return values


async def get_business_settings(session: AsyncSession) -> BusinessSettings:
    values = await ensure_app_settings(session)

    def value(field: str) -> str:
        return values.get(KEYS[field], "").strip()

    return BusinessSettings(
        tech_integration_category_id=_to_int(value("tech_integration_category_id")),
        implementation_category_id=_to_int(value("implementation_category_id")),
        cr_start_category_id=_to_int(value("cr_start_category_id")),
        support_category_id=_to_int(value("support_category_id")),
        field_monthly_amount=value("field_monthly_amount"),
        field_machines_count=value("field_machines_count"),
        field_integration_1c=value("field_integration_1c"),
        field_implementation_responsible_id=value("field_implementation_responsible_id"),
        field_source_deal_id=value("field_source_deal_id"),
        field_sales_bonus_user_id=value("field_sales_bonus_user_id"),
        cr_start_boolean_fields=[
            item.strip()
            for item in value("cr_start_boolean_fields").split(",")
            if item.strip()
        ],
        field_client_works=value("field_client_works"),
        task_training_bonus_field=value("task_training_bonus_field"),
        field_module=value("field_module") or "ufCrm_1650618044049",
        field_integration_amount=value("field_integration_amount"),
    )


async def get_app_settings_dict(session: AsyncSession) -> dict:
    return asdict(await get_business_settings(session))


async def save_app_settings(session: AsyncSession, data: dict) -> BusinessSettings:
    values = await ensure_app_settings(session)

    for field, env_name in KEYS.items():
        if field not in data:
            continue

        raw = data[field]
        if field == "cr_start_boolean_fields":
            raw = ",".join(raw or []) if isinstance(raw, list) else str(raw or "")
        elif raw is None:
            raw = ""
        else:
            raw = str(raw)

        row = await session.get(AppSetting, env_name)
        if row is None:
            row = AppSetting(key=env_name, value=raw)
            session.add(row)
        else:
            row.value = raw
        values[env_name] = raw

    await session.commit()
    return await get_business_settings(session)
