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
    task_1c_type_field: str = "UF_TYPE_TASK_1C"
    task_1c_errors_project_id: int | None = Field(default=None, gt=0)
    field_module: str = "ufCrm_1650618044049"
    field_integration_amount: str = ""
    field_planned_subscription_date: str = "ufCrm_1774423053267"
    field_billing_start_date: str = ""
    field_deal_current_status: str = "ufCrm_1775543806700"
    field_timely_request_percent: str = "ufCrm_1672064093071"
    field_implementation_planned_billing_start: str = "ufCrm_1741339373"
    field_implementation_planned_subscription: str = "ufCrm_1741339385"
    field_salesperson: str = "ufCrm_1636967212"
    field_first_training_date: str = "ufCrm_1636966670"
    field_second_training_date: str = "ufCrm_1636966749"
    field_reports_training_date: str = "ufCrm_1636966700"
    field_cr_company_id: str = "ufCrm_1737441008"


class BitrixDealField(BaseModel):
    code: str
    title: str
    field_type: str = ""
