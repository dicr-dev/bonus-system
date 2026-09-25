import json

from sqlalchemy import or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.models.deal import Deal
from cr_portal.models.task import BitrixTask
from cr_portal.models.user import User
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.employee_scope import employee_is_in_department


async def task_1c_check_report(
    session: AsyncSession,
    *,
    task_bitrix_ids: list[int] | None = None,
) -> dict:
    business = await get_business_settings(session)
    developers = [
        user.bitrix_id
        for user in (await session.execute(select(User).where(User.is_active.is_(True)))).scalars()
        if employee_is_in_department(user, "Разработка 1С")
    ]
    if not developers:
        return {"tasks": []}

    project_id = business.task_1c_errors_project_id
    project_is_missing = (
        BitrixTask.group_id != project_id
        if project_id is not None
        else true()
    )
    tasks = (await session.execute(
        select(BitrixTask)
        .where(
            BitrixTask.responsible_bitrix_id.in_(developers),
            or_(BitrixTask.task_1c_type_missing.is_(True), project_is_missing),
        )
        .order_by(BitrixTask.bitrix_id.desc())
    )).scalars().all()
    deal_ids = {
        deal_id
        for task in tasks
        for deal_id in _deal_ids(task.crm_deal_ids_json)
    }
    deals_by_bitrix_id = {
        deal.bitrix_id: deal
        for deal in (await session.execute(
            select(Deal).where(Deal.bitrix_id.in_(deal_ids))
        )).scalars()
    } if deal_ids else {}
    user_ids = {
        user_id
        for task in tasks
        for user_id in (task.creator_bitrix_id, task.responsible_bitrix_id)
        if user_id is not None
    }
    users_by_bitrix_id = {
        user.bitrix_id: user.full_name
        for user in (await session.execute(
            select(User).where(User.bitrix_id.in_(user_ids))
        )).scalars()
    } if user_ids else {}

    rows = [
        {
            "task_bitrix_id": task.bitrix_id,
            "title": task.title,
            "group_id": task.group_id,
            "responsible_bitrix_id": task.responsible_bitrix_id,
            "deal_bitrix_id": deal.bitrix_id if (deal := _task_deal(task, deals_by_bitrix_id)) else None,
            "deal_title": deal.title if deal else None,
            "deal_funnel": deal.funnel if deal else None,
            "creator_name": users_by_bitrix_id.get(task.creator_bitrix_id),
            "responsible_name": users_by_bitrix_id.get(task.responsible_bitrix_id),
            "created_time": task.created_time,
            "in_1c_project": task.group_id == project_id,
            "has_1c_type": not task.task_1c_type_missing,
            "status": task.status,
        }
        for task in tasks
    ]
    if task_bitrix_ids is not None:
        rows_by_id = {row["task_bitrix_id"]: row for row in rows}
        rows = [rows_by_id[task_id] for task_id in task_bitrix_ids if task_id in rows_by_id]
    return {"tasks": rows}


def _deal_ids(value: str) -> list[int]:
    try:
        values = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return [item for item in values if isinstance(item, int)] if isinstance(values, list) else []


def _task_deal(task: BitrixTask, deals_by_bitrix_id: dict[int, Deal]) -> Deal | None:
    return next((deals_by_bitrix_id[deal_id] for deal_id in _deal_ids(task.crm_deal_ids_json) if deal_id in deals_by_bitrix_id), None)
