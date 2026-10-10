def test_current_health_route_exists():
    from pathlib import Path
    main = Path("backend/app/main.py").read_text()
    assert '@app.get("/health")' in main
