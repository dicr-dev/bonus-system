from pydantic import BaseModel, Field
from typing import Literal


class AppSettingsPayload(BaseModel):
    task_training_yes_value: str = ""
    task_training_date_field: Literal["CLOSED_DATE", "DEADLINE"] = "DEADLINE"
    overtime_project_id: int | None = Field(default=None, gt=0)
    overtime_department_ids: str = Field(default="", pattern=r"^\s*(\d+\s*(,\s*\d+\s*)*)?$")
    task_overtime_hours_field: str = ""
    overtime_time_priority: Literal["manual", "tracker"] = "manual"
    tech_integration_category_id: int | None = None
    implementation_category_id: int | None = None
    cr_start_category_id: int | None = None
    support_category_id: int | None = None

    field_monthly_amount: str = ""
    field_machines_count: str = ""
    field_integration_1c: str = ""
    field_implementation_responsible_id: str = ""
    field_source_deal_id: str = ""
    field_sales_bonus_user_id: str = ""
    cr_start_boolean_fields: list[str] = Field(default_factory=list)
    cr_start_implementation_modules: list[str] = Field(
        default_factory=lambda: ["КР Старт ТМ", "КР Старт Эксплуатация"]
    )
    field_client_works: str = ""
    task_training_bonus_field: str = ""
    field_module: str = "ufCrm_1650618044049"
    field_integration_amount: str = ""
    field_planned_subscription_date: str = "ufCrm_1774423053267"
