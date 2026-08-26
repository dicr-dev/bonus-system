from typing import Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "CR Integration Portal"
    APP_VERSION: str = "1.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str
    REDIS_URL: str
    FRONTEND_URL: str = "http://localhost:3000"
    SESSION_SECRET: str = "dev-only-change-me"
    CORS_ORIGINS: list[str] = Field(default_factory=list)
    BITRIX_BASE_URL: str = "https://bx.crg.im"
    BITRIX_CLIENT_ID: str = ""
    BITRIX_CLIENT_SECRET: str = ""
    BITRIX_REDIRECT_URI: str = ""
    BITRIX_WEBHOOK_URL: str = ""
    BITRIX_TECH_INTEGRATION_CATEGORY_ID: int | None = None
    BITRIX_IMPLEMENTATION_CATEGORY_ID: int | None = None
    BITRIX_CR_START_CATEGORY_ID: int | None = None
    BITRIX_SUPPORT_CATEGORY_ID: int | None = None
    BITRIX_FIELD_MONTHLY_AMOUNT: str = ""
    BITRIX_FIELD_MACHINES_COUNT: str = ""
    BITRIX_FIELD_INTEGRATION_1C: str = ""
    BITRIX_FIELD_IMPLEMENTATION_RESPONSIBLE_ID: str = ""
    BITRIX_FIELD_SOURCE_DEAL_ID: str = ""
    BITRIX_FIELD_SALES_BONUS_USER_ID: str = ""
    BITRIX_CR_START_BOOLEAN_FIELDS: str = ""
    BITRIX_FIELD_CLIENT_WORKS: str = ""
    BITRIX_TASK_TRAINING_BONUS_FIELD: str = ""

    @field_validator(
        "BITRIX_TECH_INTEGRATION_CATEGORY_ID",
        "BITRIX_IMPLEMENTATION_CATEGORY_ID",
        "BITRIX_CR_START_CATEGORY_ID",
        "BITRIX_SUPPORT_CATEGORY_ID",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        return None if value == "" else value

    @property
    def cr_start_boolean_fields(self) -> list[str]:
        return [x.strip() for x in self.BITRIX_CR_START_BOOLEAN_FIELDS.split(",") if x.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

settings = Settings()
