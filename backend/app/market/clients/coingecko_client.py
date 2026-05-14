from backend.app.market.core.config import settings
from backend.app.market.core.cache import cache
from backend.app.market.core.http import get_json

class CoinGeckoClient:
    def __init__(self):
        self.base_url = settings.coingecko_base_url.rstrip("/")
        self.api_key = settings.coingecko_api_key

    def _headers(self):
        return {"x-cg-demo-api-key": self.api_key} if self.api_key else {}

    def markets(self, ids: list[str], vs_currency: str = "brl"):
        clean_ids = ",".join([x.strip().lower() for x in ids if x.strip()])
        key = f"cg:markets:{clean_ids}:{vs_currency}"
        cached = cache.get(key)
        if cached:
            return cached
        data = get_json(f"{self.base_url}/coins/markets", params={"vs_currency": vs_currency, "ids": clean_ids, "price_change_percentage": "30d,90d,1y"}, headers=self._headers(), timeout=settings.request_timeout)
        cache.set(key, data, settings.cache_ttl_seconds)
        return data

    def market_chart(self, coin_id: str, days: int = 365, vs_currency: str = "brl"):
        key = f"cg:chart:{coin_id}:{days}:{vs_currency}"
        cached = cache.get(key)
        if cached:
            return cached
        data = get_json(f"{self.base_url}/coins/{coin_id}/market_chart", params={"vs_currency": vs_currency, "days": days, "interval": "daily"}, headers=self._headers(), timeout=settings.request_timeout)
        cache.set(key, data, settings.cache_ttl_seconds)
        return data
