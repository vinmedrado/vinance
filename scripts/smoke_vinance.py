from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("VINANCE_BASE_URL", "http://localhost:8000").rstrip("/")


def request(method: str, path: str, payload: dict | None = None, token: str | None = None) -> tuple[int, dict | str]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, raw


def assert_ok(name: str, status: int, data: dict | str, allowed=(200, 201)) -> None:
    if status not in allowed:
        raise AssertionError(f"{name} failed: HTTP {status} -> {data}")
    print(f"OK {name}: HTTP {status}")


def main() -> int:
    for i in range(20):
        status, data = request("GET", "/health")
        if status == 200:
            break
        time.sleep(2)
    assert_ok("health", status, data)

    status, login = request("POST", "/api/auth/login", {"email": "demo@vinance.local", "password": "demo"})
    assert_ok("demo login", status, login)
    token = login["access_token"] if isinstance(login, dict) else None

    status, me = request("GET", "/api/auth/me", token=token)
    assert_ok("auth me", status, me)

    status, markets = request("GET", "/api/quant/markets?limit=5", token=token)
    assert_ok("quant markets", status, markets)

    status, decision = request("POST", "/api/quant/investment-decision", {
        "monthly_income": 9000,
        "monthly_expenses": 5200,
        "cash_available": 35000,
        "emergency_reserve_current": 22000,
        "risk_profile": "moderado",
        "horizon_months": 36,
        "objective": "crescimento patrimonial com controle de risco",
    }, token=token)
    assert_ok("investment decision", status, decision)

    status, backtest = request("POST", "/api/quant/backtest/run", {
        "ticker": "BOVA11",
        "initial_capital": 15000,
        "monthly_contribution": 800,
        "strategy": "momentum_quality_risk_control",
        "horizon_months": 36,
        "risk_profile": "moderado",
    }, token=token)
    assert_ok("quant backtest", status, backtest)

    status, runs = request("GET", "/api/quant/runs?limit=5", token=token)
    assert_ok("quant runs", status, runs)

    print("\nVINANCE SMOKE TEST OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VINANCE SMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
