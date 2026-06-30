from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "DigitalCard API"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    secret_key: SecretStr = Field(min_length=32)
    database_url: str = "sqlite:///./data/digitalcard.db"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    login_max_attempts: int = Field(default=5, ge=3, le=20)
    login_lock_minutes: int = Field(default=15, ge=1, le=1440)
    jwt_issuer: str = "digitalcard-api"
    jwt_audience: str = "digitalcard-admin"
    refresh_cookie_name: str = "digitalcard_refresh"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    if (
        settings.app_env == "production"
        and "change-this" in settings.secret_key.get_secret_value().lower()
    ):
        raise ValueError("SECRET_KEY must be replaced before running in production")
    return settings
