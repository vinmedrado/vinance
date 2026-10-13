from __future__ import annotations

import json
import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.auth.schemas import UserCreate, UserLogin
from backend.app.core.config import Settings
from backend.app.core.logging import StructuredFormatter
from backend.app.financial.health import classify_financial_health
from backend.app.intelligence.services.budget_advisor_service import build_budget_items


def _score(ticker: str, score: object, price: object) -> SimpleNamespace:
    return SimpleNamespace(ticker=ticker, market="FII", score_total=score, price=price)


@pytest.mark.parametrize("budget", [Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("0")])
def test_budget_advisor_rejects_non_finite_or_non_positive_budget(budget: Decimal) -> None:
    with pytest.raises(ValueError, match="budget"):
        build_budget_items([_score("SAFE11", 80, 10)], budget=budget, limit=10)


def test_budget_advisor_skips_invalid_candidates_and_zero_quantity() -> None:
    items = build_budget_items(
        [
            _score("NO_SCORE11", None, 10),
            _score("NO_PRICE11", 80, None),
            _score("NAN11", Decimal("NaN"), 10),
            _score("EXPENSIVE11", 90, 101),
            _score("SAFE11", 85, 20),
        ],
        budget=Decimal("100"),
        limit=10,
    )

    assert [item.ticker for item in items] == ["SAFE11"]
    assert items[0].quantity_possible == 5


def test_budget_advisor_deduplicates_assets_case_insensitively() -> None:
    items = build_budget_items(
        [_score("DUPL11", 90, 20), _score("dupl11", 80, 20)],
        budget=Decimal("100"),
        limit=10,
    )

    assert len(items) == 1
    assert items[0].ticker == "DUPL11"


def test_budget_advisor_handles_high_supported_budget_without_overflow() -> None:
    items = build_budget_items(
        [_score("SAFE11", 80, 1)],
        budget=Decimal("1000000000000"),
        limit=1,
    )

    assert items[0].quantity_possible == 1_000_000_000_000
    assert items[0].invested_amount == Decimal("1000000000000.00")


def test_budget_advisor_rejects_invalid_profile() -> None:
    with pytest.raises(ValueError, match="profile inválido"):
        build_budget_items(
            [_score("SAFE11", 80, 10)],
            budget=Decimal("100"),
            limit=10,
            profile="DROP TABLE users",
        )


def test_login_and_registration_forbid_oversized_or_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        UserLogin.model_validate({"email": "qa@example.com", "password": "x" * 129})
    with pytest.raises(ValidationError):
        UserLogin.model_validate({"email": "qa@example.com", "password": "valid-pass", "admin": True})
    with pytest.raises(ValidationError):
        UserCreate.model_validate({"email": "qa@example.com", "password": "valid-pass", "token": "nope"})


def test_production_settings_reject_placeholder_credentials_and_local_cors() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+asyncpg://vinance:vinance@postgres:5432/vinance",
            redis_url="redis://redis:6379/0",
            secret_key="a" * 40,
            cors_origins="http://localhost:3000",
        )

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "CORS_ORIGINS" in message


def test_production_settings_accept_explicit_secure_values() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        database_url="postgresql+asyncpg://app:strong-password@db.internal:5432/vinance",
        redis_url="redis://app:strong-password@redis.internal:6379/0",
        secret_key="5f98b98df53b425d8f7436d5ac21cbfdc886829c4f88b9bb",
        cors_origins="https://vinance.example.com",
        trusted_hosts="vinance.example.com",
    )

    assert settings.is_production is True


def test_production_settings_reject_non_https_public_origin() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+asyncpg://app:strong-password@db.internal:5432/vinance",
            redis_url="redis://app:strong-password@redis.internal:6379/0",
            secret_key="5f98b98df53b425d8f7436d5ac21cbfdc886829c4f88b9bb",
            cors_origins="http://vinance.example.com",
            trusted_hosts="vinance.example.com",
        )


def test_production_example_placeholders_fail_closed() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+asyncpg://app:replace-with-password@postgres:5432/vinance",
            redis_url="redis://:replace-with-password@redis:6379/0",
            secret_key="replace-with-a-strong-random-secret-at-least-32-bytes",
            cors_origins="https://vinance.example.invalid",
            trusted_hosts="vinance.example.invalid",
        )

    message = str(exc_info.value)
    for field in ("DATABASE_URL", "REDIS_URL", "SECRET_KEY", "CORS_ORIGINS", "TRUSTED_HOSTS"):
        assert field in message


@pytest.mark.parametrize(
    ("field", "value"),
    (("debug", True), ("demo_mode_enabled", True)),
)
def test_production_rejects_debug_and_demo_modes(field: str, value: bool) -> None:
    values = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://app:strong-password@db.internal:5432/vinance",
        "redis_url": "redis://app:strong-password@redis.internal:6379/0",
        "secret_key": "5f98b98df53b425d8f7436d5ac21cbfdc886829c4f88b9bb",
        "cors_origins": "https://vinance.example.com",
        "trusted_hosts": "vinance.example.com",
        field: value,
    }
    with pytest.raises(ValidationError, match=field.upper()):
        Settings(_env_file=None, **values)


def test_cors_wildcard_is_rejected_with_credentials_in_every_environment() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(_env_file=None, cors_origins="*")


def test_structured_logs_redact_tokens_passwords_cookies_and_keys() -> None:
    record = logging.LogRecord(
        name="phase38",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            "Authorization: Bearer super.secret.token "
            'password="dont-log-me" access_token=also-secret '
            "cookie=session-secret api_key=provider-secret"
        ),
        args=(),
        exc_info=None,
    )
    payload = json.loads(StructuredFormatter().format(record))

    serialized = json.dumps(payload)
    for secret in ("super.secret.token", "dont-log-me", "also-secret", "session-secret", "provider-secret"):
        assert secret not in serialized
    assert "[REDACTED]" in serialized


def test_financial_health_classification_has_no_legacy_model_dependency() -> None:
    classification, diagnosis = classify_financial_health(0.45, 6.5, 2500, 10000)
    assert classification == "seguro"
    assert "saudável" in diagnosis


def test_health_is_liveness_even_when_a_dependency_is_unavailable(monkeypatch) -> None:
    from backend.app import main as main_module

    async def database_unavailable() -> bool:
        return False

    async def redis_available() -> bool:
        return True

    monkeypatch.setattr(main_module, "validate_database_connection", database_unavailable)
    monkeypatch.setattr(main_module, "validate_redis_connection", redis_available)

    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["api"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_ready_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    from backend.app import main as main_module

    async def database_unavailable() -> bool:
        return False

    async def redis_available() -> bool:
        return True

    monkeypatch.setattr(main_module, "validate_database_connection", database_unavailable)
    monkeypatch.setattr(main_module, "validate_redis_connection", redis_available)

    with TestClient(main_module.app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "api": "ok",
        "database": "error",
        "redis": "ok",
        "schema": "error",
    }


def test_ready_requires_database_schema_to_match_application_head(monkeypatch) -> None:
    from backend.app import main as main_module

    async def available() -> bool:
        return True

    async def incompatible_schema() -> SimpleNamespace:
        return SimpleNamespace(compatible=False)

    monkeypatch.setattr(main_module, "validate_database_connection", available)
    monkeypatch.setattr(main_module, "validate_redis_connection", available)
    monkeypatch.setattr(main_module, "schema_revision_status", incompatible_schema)

    with TestClient(main_module.app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["schema"] == "error"


def test_ready_succeeds_when_dependencies_and_schema_are_compatible(monkeypatch) -> None:
    from backend.app import main as main_module

    async def available() -> bool:
        return True

    async def compatible_schema() -> SimpleNamespace:
        return SimpleNamespace(compatible=True)

    monkeypatch.setattr(main_module, "validate_database_connection", available)
    monkeypatch.setattr(main_module, "validate_redis_connection", available)
    monkeypatch.setattr(main_module, "schema_revision_status", compatible_schema)

    with TestClient(main_module.app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "api": "ok",
        "database": "ok",
        "redis": "ok",
        "schema": "ok",
    }


@pytest.mark.parametrize(
    "query",
    [
        "budget=0",
        "budget=-1",
        "budget=NaN",
        "budget=1000000000001",
        "budget=100&market=FII%27%3BDELETE%20FROM%20users--",
    ],
)
def test_budget_advisor_rejects_invalid_common_inputs_before_engine(query: str) -> None:
    from backend.app import main as main_module
    from backend.app.auth.dependencies import get_current_user
    from backend.app.core.database import get_session

    async def current_user_override() -> SimpleNamespace:
        return SimpleNamespace(id=38, email="phase38@example.com", is_active=True)

    async def session_override():
        yield object()

    main_module.app.dependency_overrides[get_current_user] = current_user_override
    main_module.app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(main_module.app) as client:
            response = client.get(f"/api/intelligence/budget-advisor?{query}")
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 422
