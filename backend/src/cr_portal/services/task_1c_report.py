import json
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.app_settings import AppSetting
from cr_portal.models.task import BitrixTask
from cr_portal.models.user import User
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.task_kpi import field_value

TYPE_METADATA_KEY = "monthly_rating.task_type_metadata"


def _display_type(value, labels: dict[str, str]) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        mapping = value
        value = mapping.get("VALUE") or mapping.get("value")
        value = value or mapping.get("NAME") or mapping.get("name") or mapping
    if isinstance(value, (list, tuple, set)):
        values = [_display_type(item, labels) for item in value]
        return ", ".join(item for item in values if item) or None
    return labels.get(str(value), str(value))


def _labels(value: str) -> dict[str, str]:
    try:
        payload = json.loads(value)
        labels = payload.get("labels", {})
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(labels, dict):
        return {}
    return {str(key): str(label) for key, label in labels.items()}


async def task_1c_report(session: AsyncSession) -> dict:
    business = await get_business_settings(session)
    cached_labels = await session.get(AppSetting, TYPE_METADATA_KEY)
    labels = _labels(cached_labels.value) if cached_labels else {}
    selected_ids = set(business.task_1c_report_user_ids)
    developers = []
    if selected_ids:
        developers = (
            await session.execute(select(User).where(User.id.in_(selected_ids)))
        ).scalars().all()
    developers_by_bitrix_id = {user.bitrix_id: user for user in developers}
    if not developers_by_bitrix_id:
        return {"tasks": [], "developers": []}

    tasks = (await session.execute(
        select(BitrixTask).where(BitrixTask.responsible_bitrix_id.in_(developers_by_bitrix_id)).order_by(
            BitrixTask.created_time.desc(), BitrixTask.bitrix_id.desc()
        )
    )).scalars().all()
    user_ids = {task.creator_bitrix_id for task in tasks if task.creator_bitrix_id is not None}
    users = []
    if user_ids:
        users = (
            await session.execute(select(User).where(User.bitrix_id.in_(user_ids)))
        ).scalars()
    names = {
        user.bitrix_id: user.full_name
        for user in users
    }
    status_counts = Counter((task.responsible_bitrix_id, task.status) for task in tasks)
    def task_type(task: BitrixTask) -> str | None:
        try:
            payload = json.loads(task.raw_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return None
        return _display_type(field_value(payload, business.task_1c_type_field), labels)
    return {
        "tasks": [
            {
                "task_bitrix_id": task.bitrix_id,
                "title": task.title,
                "group_id": task.group_id,
                "responsible_bitrix_id": task.responsible_bitrix_id,
                "creator_name": names.get(task.creator_bitrix_id),
                "responsible_name": developers_by_bitrix_id[task.responsible_bitrix_id].full_name,
                "created_time": task.created_time,
                "deadline": task.deadline,
                "status": task.status,
                "task_1c_type": task_type(task),
            }
            for task in tasks
        ],
        "developers": [
            {
                "user_id": str(user.id), "full_name": user.full_name,
                "todo": status_counts[(user.bitrix_id, 2)],
                "in_progress": status_counts[(user.bitrix_id, 3)],
                "awaiting_review": status_counts[(user.bitrix_id, 4)],
                "completed": status_counts[(user.bitrix_id, 5)],
            }
            for user in sorted(developers, key=lambda item: item.full_name.casefold())
        ],
    }
