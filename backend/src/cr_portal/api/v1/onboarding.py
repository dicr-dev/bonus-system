from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, current_user, db_session
from cr_portal.models.onboarding import OnboardingAssignment, OnboardingPlanSection, OnboardingPlanTask, OnboardingTask
from cr_portal.models.user import User
from cr_portal.schemas.onboarding import OnboardingAssignmentResponse, OnboardingPlanInput, OnboardingPlanSectionResponse, OnboardingPlanTaskResponse, OnboardingTaskResponse, OnboardingTaskUpdate

router = APIRouter()

async def _assignment_response(session: AsyncSession, assignment: OnboardingAssignment) -> OnboardingAssignmentResponse:
    employee = await session.get(User, assignment.employee_id)
    assigned_by = await session.get(User, assignment.assigned_by_id)
    tasks = (await session.execute(select(OnboardingTask).where(OnboardingTask.assignment_id == assignment.id).order_by(OnboardingTask.position))).scalars().all()
    return OnboardingAssignmentResponse(
        id=assignment.id, employee_id=assignment.employee_id, employee_name=employee.full_name if employee else "Удалённый сотрудник",
        assigned_by_name=assigned_by.full_name if assigned_by else "Удалённый пользователь", created_at=assignment.created_at,
        tasks=[OnboardingTaskResponse.model_validate(task) for task in tasks],
    )


async def _plan_response(session: AsyncSession) -> list[OnboardingPlanSectionResponse]:
    sections = (await session.execute(select(OnboardingPlanSection).order_by(OnboardingPlanSection.position))).scalars().all()
    result = []
    for section in sections:
        tasks = (await session.execute(select(OnboardingPlanTask).where(OnboardingPlanTask.section_id == section.id).order_by(OnboardingPlanTask.position))).scalars().all()
        result.append(OnboardingPlanSectionResponse(id=section.id, title=section.title, details=section.details, position=section.position, tasks=[OnboardingPlanTaskResponse(id=task.id, title=task.title, details=task.details, position=task.position) for task in tasks]))
    return result


@router.get("/my", response_model=OnboardingAssignmentResponse | None)
async def my_onboarding(session: AsyncSession = Depends(db_session), user=Depends(current_user)):
    assignment = (await session.execute(select(OnboardingAssignment).where(OnboardingAssignment.employee_id == user.id))).scalar_one_or_none()
    return await _assignment_response(session, assignment) if assignment else None


@router.patch("/tasks/{task_id}", response_model=OnboardingTaskResponse)
async def update_task(task_id: UUID, data: OnboardingTaskUpdate, session: AsyncSession = Depends(db_session), user=Depends(current_user)):
    task = await session.get(OnboardingTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Пункт адаптации не найден")
    assignment = await session.get(OnboardingAssignment, task.assignment_id)
    if assignment is None or assignment.employee_id != user.id:
        raise HTTPException(status_code=403, detail="Можно изменять только свои пункты адаптации")
    if data.is_completed and not (data.comment or "").strip():
        raise HTTPException(status_code=422, detail="Укажите итоговый комментарий")
    task.is_completed = data.is_completed
    task.comment = data.comment.strip() if data.comment else None
    task.completed_at = datetime.now(timezone.utc) if data.is_completed else None
    await session.commit()
    await session.refresh(task)
    return OnboardingTaskResponse.model_validate(task)


@router.get("/", response_model=list[OnboardingAssignmentResponse])
async def assignments(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    rows = (await session.execute(select(OnboardingAssignment).order_by(OnboardingAssignment.created_at.desc()))).scalars().all()
    return [await _assignment_response(session, assignment) for assignment in rows]


@router.get("/template", response_model=list[OnboardingPlanSectionResponse])
async def template(session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    return await _plan_response(session)


@router.put("/template", response_model=list[OnboardingPlanSectionResponse])
async def update_template(data: OnboardingPlanInput, session: AsyncSession = Depends(db_session), _admin=Depends(admin_user)):
    await session.execute(delete(OnboardingPlanTask))
    await session.execute(delete(OnboardingPlanSection))
    await session.flush()
    for section_position, section_data in enumerate(data.sections, 1):
        section = OnboardingPlanSection(title=section_data.title.strip(), details=section_data.details.strip() if section_data.details else None, position=section_position)
        session.add(section)
        await session.flush()
        for task_position, task_data in enumerate(section_data.tasks, 1):
            session.add(OnboardingPlanTask(section_id=section.id, title=task_data.title.strip(), details=task_data.details.strip() if task_data.details else None, position=task_position))
    await session.commit()
    return await _plan_response(session)


@router.post("/assign/{employee_id}", response_model=OnboardingAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign(employee_id: UUID, session: AsyncSession = Depends(db_session), admin=Depends(admin_user)):
    employee = await session.get(User, employee_id)
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=422, detail="Выберите активного сотрудника")
    exists = (await session.execute(select(OnboardingAssignment.id).where(OnboardingAssignment.employee_id == employee_id))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Адаптация этому сотруднику уже назначена")
    assignment = OnboardingAssignment(employee_id=employee_id, assigned_by_id=admin.id)
    session.add(assignment)
    await session.flush()
    sections = (await session.execute(select(OnboardingPlanSection).order_by(OnboardingPlanSection.position))).scalars().all()
    position = 0
    for section in sections:
        tasks = (await session.execute(select(OnboardingPlanTask).where(OnboardingPlanTask.section_id == section.id).order_by(OnboardingPlanTask.position))).scalars().all()
        for task in tasks:
            position += 1
            session.add(OnboardingTask(assignment_id=assignment.id, section=section.title, section_details=section.details, title=task.title, details=task.details, position=position))
    await session.commit()
    await session.refresh(assignment)
    return await _assignment_response(session, assignment)
