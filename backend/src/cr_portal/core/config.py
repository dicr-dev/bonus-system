from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    APP_NAME: str = "CR Integration Portal"
    APP_VERSION: str = "0.1.0"

    DEBUG: bool = True

    DATABASE_URL: str = (
        "postgresql+psycopg://bonus_user:bonus_password@localhost:5432/bonus_system"
    )

    REDIS_URL: str = "redis://localhost:6379/0"

    BITRIX_URL: str = ""
    BITRIX_CLIENT_ID: str = ""
    BITRIX_CLIENT_SECRET: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()