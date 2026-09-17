from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.task import BitrixTask
from cr_portal.models.user import User
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.employee_scope import employee_is_in_department

TASK_1C_ERRORS_START = datetime(2025, 11, 1, tzinfo=ZoneInfo("Europe/Moscow")).astimezone(UTC)


async def task_1c_errors_report(
    session: AsyncSession,
    *,
    current_user: User,
    employee_id: UUID | None = None,
) -> dict:
    business = await get_business_settings(session)
    if business.task_1c_errors_project_id is None:
        return {"tasks": []}
    implementation_users = [
        user
        for user in (await session.execute(select(User).where(User.is_active.is_(True)))).scalars()
        if employee_is_in_department(user, "Отдел внедрения")
    ]
    if current_user.is_admin:
        allowed_users = implementation_users
        if employee_id is not None:
            allowed_users = [user for user in allowed_users if user.id == employee_id]
    elif employee_is_in_department(current_user, "Отдел внедрения"):
        allowed_users = [current_user]
    else:
        raise PermissionError("Блок доступен только сотрудникам отдела внедрения")

    users_by_bitrix_id = {user.bitrix_id: user for user in allowed_users}
    if not users_by_bitrix_id:
        return {"tasks": []}

    tasks = (await session.execute(
        select(BitrixTask)
        .where(
            BitrixTask.creator_bitrix_id.in_(users_by_bitrix_id),
            BitrixTask.group_id == business.task_1c_errors_project_id,
            BitrixTask.task_1c_type_missing.is_(True),
            BitrixTask.start_time > TASK_1C_ERRORS_START,
        )
        .order_by(BitrixTask.start_time.desc(), BitrixTask.bitrix_id.desc())
    )).scalars().all()
    return {"tasks": [
        {
            "task_bitrix_id": task.bitrix_id,
            "title": task.title,
            "group_id": task.group_id,
            "responsible_bitrix_id": task.responsible_bitrix_id,
            "creator_id": users_by_bitrix_id[task.creator_bitrix_id].id,
            "creator_name": users_by_bitrix_id[task.creator_bitrix_id].full_name,
            "start_time": task.start_time,
            "status": task.status,
        }
        for task in tasks
    ]}
