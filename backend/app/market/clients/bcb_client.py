from datetime import date, timedelta
from backend.app.market.core.config import settings
from backend.app.market.core.cache import cache
from backend.app.market.core.http import get_json

BCB_SERIES = {
    "selic": {"code": "432", "name": "Meta Selic"},
    "ipca": {"code": "433", "name": "IPCA"},
    "dolar": {"code": "1", "name": "Dólar comercial venda"},
    "cdi": {"code": "12", "name": "CDI"},
}

class BCBClient:
    def __init__(self):
        self.base_url = settings.bcb_base_url.rstrip("/")

    def serie(self, code: str, days: int = 365):
        end = date.today(); start = end - timedelta(days=days)
        key = f"bcb:serie:{code}:{days}"
        cached = cache.get(key)
        if cached:
            return cached
        params = {"formato": "json", "dataInicial": start.strftime("%d/%m/%Y"), "dataFinal": end.strftime("%d/%m/%Y")}
        data = get_json(f"{self.base_url}.{code}/dados", params=params, timeout=settings.request_timeout)
        cache.set(key, data, settings.cache_ttl_seconds)
        return data

    def macro_snapshot(self):
        snapshot = {}
        for key, meta in BCB_SERIES.items():
            try:
                values = self.serie(meta["code"], days=90)
                last = values[-1] if values else {}
                value = float(str(last.get("valor", "0")).replace(",", ".")) if last else None
                snapshot[key] = {"code": meta["code"], "name": meta["name"], "date": last.get("data"), "value": value}
            except Exception as exc:
                snapshot[key] = {"code": meta["code"], "name": meta["name"], "date": None, "value": None, "error": str(exc)}
        return snapshot
