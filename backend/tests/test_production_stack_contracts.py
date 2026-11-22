from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_production_compose_has_complete_runtime_and_single_public_edge() -> None:
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    for service in ("postgres", "redis", "migrate", "backend", "celery_worker", "celery_beat", "frontend"):
        assert f"  {service}:" in compose
    assert '"127.0.0.1:${EDGE_PORT:-8080}:8080"' in compose
    assert "service_completed_successfully" in compose
    assert "alembic upgrade head && python -m backend.trading.storage.migrate upgrade" in compose
    assert "CELERY_WORKER_CONCURRENCY" in compose
    assert "networks: [internal, egress]" in compose
    assert "ml_artifacts_data:/app/data/ml_artifacts" in compose
    assert "trading_artifacts_data:/app/backend/trading/artifacts/ml_engine_v2" in compose
    assert "trading_outputs_data:/app/backend/trading/output" in compose
    assert "max-size:" in compose and "max-file:" in compose
    assert "./logs:/app/logs" not in compose
    assert "./storage:/app/storage" not in compose


def test_production_compose_separates_runtime_and_migration_database_credentials() -> None:
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")

    assert "DATABASE_URL: ${RUNTIME_DATABASE_URL:?RUNTIME_DATABASE_URL is required}" in compose
    assert "MIGRATION_DATABASE_URL: ${MIGRATION_DATABASE_URL:?MIGRATION_DATABASE_URL is required}" in compose
    migrate_block = compose.split("  migrate:", 1)[1].split("  backend:", 1)[0]
    assert "DATABASE_URL: ${MIGRATION_DATABASE_URL:?MIGRATION_DATABASE_URL is required}" in migrate_block
    assert "prepare-runtime-role.ps1" in (ROOT / "deploy-production.ps1").read_text(encoding="utf-8")


def test_production_template_declares_access_push_secrets_without_values() -> None:
    env = (ROOT / ".env.production.example").read_text(encoding="utf-8")

    for variable in (
        "ACCESS_MODE=INVITE_ONLY",
        "BOOTSTRAP_TOKEN_HASH=replace-with",
        "RUNTIME_DATABASE_URL=postgresql+asyncpg://",
        "MIGRATION_DATABASE_URL=postgresql+asyncpg://",
        "PUSH_SUBSCRIPTION_ENCRYPTION_KEY=replace-with",
        "VAPID_PUBLIC_KEY=replace-with",
        "VAPID_PRIVATE_KEY=replace-with",
        "VAPID_SUBJECT=mailto:",
    ):
        assert variable in env


def test_production_services_receive_only_server_side_access_push_configuration() -> None:
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")

    for variable in (
        "ACCESS_MODE",
        "BOOTSTRAP_TOKEN_HASH",
        "PUSH_SUBSCRIPTION_ENCRYPTION_KEY",
        "VAPID_PUBLIC_KEY",
        "VAPID_PRIVATE_KEY",
        "VAPID_SUBJECT",
        "WEB_PUSH_ENABLED",
    ):
        assert f"  {variable}:" in compose
    frontend_block = compose.split("  frontend:", 1)[1].split("  backup:", 1)[0]
    assert "VAPID_PRIVATE_KEY" not in frontend_block
    assert "PUSH_SUBSCRIPTION_ENCRYPTION_KEY" not in frontend_block


def test_deploy_gate_rejects_open_signup_and_incomplete_access_push_secrets() -> None:
    deploy = (ROOT / "deploy-production.ps1").read_text(encoding="utf-8")

    for contract in (
        'Get-DotEnvValue -Name "ACCESS_MODE"',
        'Get-DotEnvValue -Name "BOOTSTRAP_TOKEN_HASH"',
        'Get-DotEnvValue -Name "PUSH_SUBSCRIPTION_ENCRYPTION_KEY"',
        'Get-DotEnvValue -Name "VAPID_PUBLIC_KEY"',
        'Get-DotEnvValue -Name "VAPID_PRIVATE_KEY"',
        'Get-DotEnvValue -Name "VAPID_SUBJECT"',
        'Get-DotEnvValue -Name "WEB_PUSH_ENABLED"',
        'Get-DotEnvValue -Name "RUNTIME_DB_USER"',
        'Get-DotEnvValue -Name "POSTGRES_USER"',
    ):
        assert contract in deploy
    assert "ACCESS_MODE deve permanecer INVITE_ONLY" in deploy
    assert "WEB_PUSH_ENABLED deve permanecer true" in deploy


def test_nginx_is_same_origin_and_keeps_safe_frontend_cache_policy() -> None:
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "listen 8080" in nginx
    assert "location /api/" in nginx
    assert "proxy_pass http://backend:8000" in nginx
    assert "connect-src 'self'" in nginx
    assert "proxy_set_header X-Forwarded-For $remote_addr" in nginx
    assert "$proxy_add_x_forwarded_for" not in nginx
    assert "max-age=31536000, immutable" in nginx
    assert "expires -1" in nginx
    assert "location = /openapi.json { return 404; }" in nginx
    for forbidden in ("192.168.", "localhost:8000", "127.0.0.1:8000"):
        assert forbidden not in nginx


def test_index_and_hashed_assets_retain_edge_security_headers() -> None:
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    index_block = nginx.split("location = /index.html", 1)[1].split("}", 1)[0]
    assets_block = nginx.split("location /assets/", 1)[1].split("}", 1)[0]
    assert "add_header" not in index_block
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
    ):
        assert header in assets_block


def test_frontend_build_is_deterministic_and_relative_api_by_default() -> None:
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert "npm ci --legacy-peer-deps --include=dev" in dockerfile
    assert "|| npm install" not in dockerfile
    assert "ARG VITE_API_BASE_URL=" in dockerfile
    assert "ARG VITE_API_PREFIX=/api/v1" in dockerfile
    assert "nginxinc/nginx-unprivileged" in dockerfile


def test_production_template_contains_no_real_secret_or_future_domain() -> None:
    env = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "vinance.vinmedrado.com" not in env
    assert "replace-with" in env
    assert "REGISTRATION_ENABLED=false" in env
    assert "API_DOCS_ENABLED=false" in env
