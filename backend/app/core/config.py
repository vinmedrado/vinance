from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized Vinance v2 backend settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # APP
    app_name: str = "Vinance v2"
    app_version: str = "2.0.0-phase1"
    environment: Literal["local", "development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:9000"

    # DATABASE
    database_url: str = Field(default="postgresql+asyncpg://vinance:vinance@postgres:5432/vinance")
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # REDIS
    redis_url: str = "redis://redis:6379/0"
    redis_health_retries: int = 3

    # CELERY
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_timezone: str = "America/Sao_Paulo"

    # GROQ
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # SECURITY
    secret_key: str = Field(default="change-me-before-real-use", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper().strip()
        return normalized if normalized in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_security(self):
        origins = self.cors_origin_list
        if "*" in origins:
            raise ValueError("CORS_ORIGINS cannot use wildcard while credentialed requests are enabled")

        if self.is_production:
            missing = []
            database_url = (self.database_url or "").strip()
            insecure_database_markers = (
                "vinance:vinance@",
                "postgres:postgres@",
                "usuario:senha-forte@",
                "user:password@",
            )
            if not database_url or any(marker in database_url.lower() for marker in insecure_database_markers):
                missing.append("DATABASE_URL")
            redis_url = (self.redis_url or "").strip()
            if not redis_url or "usuario:senha-forte@" in redis_url.lower():
                missing.append("REDIS_URL")

            secret_key = (self.secret_key or "").strip()
            insecure_secret_markers = (
                "change-me",
                "default",
                "example",
                "phase1",
                "troque",
                "chave-segura",
                "mais-de-32",
                "placeholder",
            )
            secret_is_insecure = (
                not secret_key
                or len(secret_key) < 32
                or any(marker in secret_key.lower() for marker in insecure_secret_markers)
            )
            if secret_is_insecure:
                missing.append("SECRET_KEY")

            insecure_origins = {
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:9000",
            }
            if not origins or any(origin in insecure_origins for origin in origins):
                missing.append("CORS_ORIGINS")

            if missing:
                raise ValueError(f"Missing or insecure required production settings: {', '.join(missing)}")
        return self

    @computed_field
    @property
    def effective_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @computed_field
    @property
    def effective_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
