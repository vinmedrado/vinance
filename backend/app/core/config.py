from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

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
    demo_mode_enabled: bool = False
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:9000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    api_docs_enabled: bool | None = None
    app_commit_sha: str = "unknown"

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
    refresh_token_expire_days: int = Field(default=30, ge=1, le=365)
    refresh_cookie_name: str = "vinance_refresh"
    refresh_cookie_path: str = "/api/v1"
    registration_enabled: bool = True
    auth_rate_limit_window_seconds: int = Field(default=60, ge=10, le=3600)
    rate_limiting_enabled: bool | None = None
    login_rate_limit: int = Field(default=10, ge=1, le=1000)
    login_ip_rate_limit: int = Field(default=50, ge=1, le=5000)
    register_rate_limit: int = Field(default=5, ge=1, le=1000)
    refresh_rate_limit: int = Field(default=30, ge=1, le=5000)
    password_change_rate_limit: int = Field(default=5, ge=1, le=1000)
    invitation_rate_limit: int = Field(default=20, ge=1, le=1000)
    continuous_evaluate_rate_limit: int = Field(default=6, ge=1, le=1000)
    advisor_chat_rate_limit: int = Field(default=20, ge=1, le=1000)
    trading_mutation_rate_limit: int = Field(default=30, ge=1, le=1000)


    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper().strip()
        return normalized if normalized in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field
    @property
    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @computed_field
    @property
    def effective_api_docs_enabled(self) -> bool:
        return not self.is_production if self.api_docs_enabled is None else self.api_docs_enabled

    @computed_field
    @property
    def refresh_cookie_secure(self) -> bool:
        return self.is_production

    @computed_field
    @property
    def effective_rate_limiting_enabled(self) -> bool:
        return self.is_production if self.rate_limiting_enabled is None else self.rate_limiting_enabled

    @model_validator(mode="after")
    def validate_production_security(self):
        origins = self.cors_origin_list
        if "*" in origins:
            raise ValueError("CORS_ORIGINS cannot use wildcard while credentialed requests are enabled")

        if self.is_production:
            missing = []
            if self.debug:
                missing.append("DEBUG")
            if self.demo_mode_enabled:
                missing.append("DEMO_MODE_ENABLED")
            database_url = (self.database_url or "").strip()
            insecure_database_markers = (
                "vinance:vinance@",
                "postgres:postgres@",
                "usuario:senha-forte@",
                "user:password@",
                "replace-with",
            )
            if not database_url or any(marker in database_url.lower() for marker in insecure_database_markers):
                missing.append("DATABASE_URL")
            redis_url = (self.redis_url or "").strip()
            if not redis_url or any(
                marker in redis_url.lower()
                for marker in ("usuario:senha-forte@", "replace-with")
            ):
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
                "replace-with",
            )
            secret_is_insecure = (
                not secret_key
                or len(secret_key) < 32
                or any(marker in secret_key.lower() for marker in insecure_secret_markers)
            )
            if secret_is_insecure:
                missing.append("SECRET_KEY")

            loopback_hosts = {"localhost", "127.0.0.1", "::1"}
            parsed_origins = [urlsplit(origin) for origin in origins]
            has_public_https_origin = any(
                parsed.scheme.lower() == "https"
                and bool(parsed.hostname)
                and parsed.hostname.lower() not in loopback_hosts
                and not parsed.hostname.lower().endswith(".invalid")
                for parsed in parsed_origins
            )
            has_invalid_origin = any(
                not parsed.hostname
                or parsed.hostname.lower().endswith(".invalid")
                or (
                    parsed.scheme.lower() != "https"
                    and not (
                        parsed.scheme.lower() == "http"
                        and parsed.hostname.lower() in loopback_hosts
                    )
                )
                for parsed in parsed_origins
            )
            if not origins or not has_public_https_origin or has_invalid_origin:
                missing.append("CORS_ORIGINS")

            hosts = self.trusted_host_list
            public_hosts = [
                host
                for host in hosts
                if host.lower() not in loopback_hosts | {"testserver"}
                and not host.lower().endswith(".invalid")
            ]
            if (
                not hosts
                or "*" in hosts
                or not public_hosts
                or any(host.lower().endswith(".invalid") for host in hosts)
            ):
                missing.append("TRUSTED_HOSTS")

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
