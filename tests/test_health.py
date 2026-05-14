def test_health_routes_exist():
    from pathlib import Path
    main = Path("backend/app/main.py").read_text()
    assert '@app.get("/health")' in main
    assert '@app.get("/ready")' in main
    assert '@app.get("/live")' in main
    assert '@app.get("/metrics")' in main
