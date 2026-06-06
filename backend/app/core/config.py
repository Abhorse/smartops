from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SmartOps API"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///./smartops_dev.db"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    google_client_id: str = ""
    auth_dev_mode: bool = True
    min_supported_app_version: str = "1.0.0"
    latest_app_version: str = "1.0.0"
    min_supported_schema_version: int = 1
    android_store_url: str = ""
    ios_store_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
