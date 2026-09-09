"""Add editable onboarding template and instructions.

Revision ID: 0010_onboarding_template
Revises: 0009_onboarding
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_onboarding_template"
down_revision = "0009_onboarding"
branch_labels = None
depends_on = None

PLAN = [
    ("Логистика", ["Изучение информации по модулю", "Написание ТЗ на интеграцию", "Проверка интеграции", "Настройка кабинета", "Проведение обучения", "Прохождение тестирования по модулю"]),
    ("CR Start", ["Изучение информации по модулю", "Проверка интеграции", "Проведение обучения", "Прохождение тестирования по модулю"]),
    ("Эксплуатация", ["Изучение информации по модулю", "Написание ТЗ на интеграцию", "Проверка интеграции", "Проведение обучения", "Прохождение тестирования по модулю"]),
    ("Топливный модуль", ["Изучение информации по модулю", "Настройка кабинета", "Проведение обучения", "Прохождение тестирования по модулю"]),
    ("Загрузки", ["Изучение информации по модулю", "Настройка кабинета", "Проведение обучения", "Прохождение тестирования по модулю"]),
]


def upgrade() -> None:
    op.add_column("onboarding_tasks", sa.Column("section_details", sa.Text(), nullable=True))
    op.add_column("onboarding_tasks", sa.Column("details", sa.Text(), nullable=True))
    op.create_table("onboarding_plan_sections", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("title", sa.String(length=255), nullable=False), sa.Column("details", sa.Text(), nullable=True), sa.Column("position", sa.Integer(), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_table("onboarding_plan_tasks", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("section_id", sa.Uuid(), nullable=False), sa.Column("title", sa.String(length=500), nullable=False), sa.Column("details", sa.Text(), nullable=True), sa.Column("position", sa.Integer(), nullable=False), sa.ForeignKeyConstraint(["section_id"], ["onboarding_plan_sections.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("section_id", "position", name="uq_onboarding_plan_tasks_section_position"))
    op.create_index("ix_onboarding_plan_tasks_section_id", "onboarding_plan_tasks", ["section_id"])
    sections = sa.table("onboarding_plan_sections", sa.column("id", sa.Uuid()), sa.column("title", sa.String()), sa.column("position", sa.Integer()))
    tasks = sa.table("onboarding_plan_tasks", sa.column("id", sa.Uuid()), sa.column("section_id", sa.Uuid()), sa.column("title", sa.String()), sa.column("position", sa.Integer()))
    import uuid
    for section_position, (title, task_titles) in enumerate(PLAN, 1):
        section_id = uuid.uuid4()
        op.bulk_insert(sections, [{"id": section_id, "title": title, "position": section_position}])
        op.bulk_insert(tasks, [{"id": uuid.uuid4(), "section_id": section_id, "title": task_title, "position": task_position} for task_position, task_title in enumerate(task_titles, 1)])


def downgrade() -> None:
    op.drop_table("onboarding_plan_tasks")
    op.drop_table("onboarding_plan_sections")
    op.drop_column("onboarding_tasks", "details")
    op.drop_column("onboarding_tasks", "section_details")
