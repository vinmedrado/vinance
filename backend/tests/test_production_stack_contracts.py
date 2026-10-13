from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_production_compose_has_complete_runtime_and_single_public_edge() -> None:
    compose = (ROOT / "docker-compose.production.yml").read_text(encoding="utf-8")
    for service in ("postgres", "redis", "migrate", "backend", "celery_worker", "celery_beat", "frontend"):
        assert f"  {service}:" in compose
    assert '"127.0.0.1:${EDGE_PORT:-8080}:8080"' in compose
    assert "service_completed_successfully" in compose
    assert "CELERY_WORKER_CONCURRENCY" in compose
    assert "networks: [internal, egress]" in compose
    assert "ml_artifacts_data:/app/data/ml_artifacts" in compose
    assert "trading_artifacts_data:/app/backend/trading/artifacts/ml_engine_v2" in compose
    assert "trading_outputs_data:/app/backend/trading/output" in compose
    assert "max-size:" in compose and "max-file:" in compose
    assert "./logs:/app/logs" not in compose
    assert "./storage:/app/storage" not in compose


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
