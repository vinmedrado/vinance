from __future__ import annotations

from .metrics_base import parse_date

MIN_PRICE_ROWS = 30


def validate_price_rows(rows: list[dict]) -> tuple[bool, str]:
    if len(rows) < MIN_PRICE_ROWS:
        return False, f"dados insuficientes: {len(rows)} preços; mínimo {MIN_PRICE_ROWS}"
    for row in rows:
        close = row.get("close")
        volume = row.get("volume")
        dt = parse_date(row.get("date"))
        if close is None or float(close) <= 0:
            return False, "preço zerado ou negativo"
        if volume is not None and float(volume) < 0:
            return False, "volume negativo"
        if dt and dt > __import__("datetime").date.today():
            return False, "data futura em preços"
    return True, "ok"


def validate_metrics(metrics: dict) -> list[str]:
    issues: list[str] = []
    for key in ["retorno_7d", "retorno_30d", "retorno_90d", "retorno_180d", "retorno_365d"]:
        value = metrics.get(key)
        if value is not None and abs(float(value)) > 10:
            issues.append(f"retorno extremo suspeito em {key}")
    dy = metrics.get("dividend_yield_12m")
    if dy is not None and float(dy) > 1:
        issues.append("dividend yield extremo suspeito")
    return issues


def validate_score(score: dict) -> list[str]:
    issues: list[str] = []
    for key, value in score.items():
        if key.startswith("score_") and value is not None and not (0 <= float(value) <= 100):
            issues.append(f"{key} fora de 0-100")
    return issues
