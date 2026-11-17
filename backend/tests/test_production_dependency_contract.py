from pathlib import Path


def test_celery_redis_transport_dependencies_are_reproducible() -> None:
    requirements = (
        Path(__file__).resolve().parents[2] / "requirements.txt"
    ).read_text(encoding="utf-8").splitlines()

    normalized = {
        line.strip().lower()
        for line in requirements
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert "redis==5.2.1" in normalized
    assert "kombu==5.6.2" in normalized
