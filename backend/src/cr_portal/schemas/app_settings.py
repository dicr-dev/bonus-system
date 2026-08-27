from pydantic import BaseModel, Field


class AppSettingsPayload(BaseModel):
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
    field_client_works: str = ""
    task_training_bonus_field: str = ""
    field_module: str = "ufCrm_1650618044049"
    field_integration_amount: str = ""
