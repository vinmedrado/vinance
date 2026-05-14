
from __future__ import annotations

from decimal import Decimal
from babel.numbers import format_currency as babel_format_currency


def format_currency(value, currency: str = "BRL", locale: str = "pt_BR") -> str:
    try:
        return babel_format_currency(Decimal(str(value or 0)), currency, locale=locale)
    except Exception:
        symbol = {"BRL": "R$", "USD": "$", "EUR": "€", "BTC": "₿"}.get(currency, currency)
        return f"{symbol} {float(value or 0):,.2f}"


def convert_currency(value: float, from_currency: str, to_currency: str) -> float:
    if from_currency == to_currency:
        return float(value or 0)
    try:
        import os
        import redis
        import requests

        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        cache_key = f"fx:{from_currency}:{to_currency}"
        cached = r.get(cache_key)
        if cached:
            rate = float(cached)
        else:
            resp = requests.get(
                "https://api.frankfurter.app/latest",
                params={"from": from_currency, "to": to_currency},
                timeout=5,
            )
            resp.raise_for_status()
            rate = float(resp.json()["rates"][to_currency])
            r.setex(cache_key, 3600, str(rate))
        return float(value or 0) * rate
    except Exception:
        return float(value or 0)
