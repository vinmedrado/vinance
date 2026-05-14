from __future__ import annotations

import os
from functools import lru_cache


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    app_name: str = os.getenv("APP_NAME", "FinanceOS")
    environment: str = os.getenv("FINANCEOS_ENV", os.getenv("ENVIRONMENT", "development"))
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    dev_mode: bool = _bool(os.getenv("FINANCEOS_DEV_MODE"), default=True)
    demo_mode_enabled: bool = _bool(os.getenv("DEMO_MODE_ENABLED"), default=True)
    analytics_enabled: bool = _bool(os.getenv("ANALYTICS_ENABLED"), default=False)
    sentry_dsn_backend: str = os.getenv("SENTRY_DSN_BACKEND", "")
    secret_key: str = os.getenv("SECRET_KEY", "")
    debug: bool = _bool(os.getenv("DEBUG"), default=False)
    max_payload_bytes: int = int(os.getenv("MAX_PAYLOAD_BYTES", "1048576"))
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_for_runtime(self) -> None:
        if self.is_production:
            if self.debug:
                raise RuntimeError("DEBUG não pode estar ativo em produção.")
            if not self.secret_key or self.secret_key in {"CHANGE_THIS_SECRET_IN_PRODUCTION", "local-dev-secret-change-me"}:
                raise RuntimeError("SECRET_KEY forte é obrigatório em produção.")
            if "*" in self.cors_origins:
                raise RuntimeError("CORS wildcard não permitido em produção.")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
