from backend.app.market.core.config import settings
from backend.app.market.core.cache import cache
from backend.app.market.core.http import get_json

class BrapiClient:
    def __init__(self):
        self.base_url = settings.brapi_base_url.rstrip("/")
        self.token = settings.brapi_token

    def _params(self, extra=None):
        params = dict(extra or {})
        if self.token:
            params["token"] = self.token
        return params

    def quote(self, tickers: list[str], range_: str = "1y", interval: str = "1d"):
        symbols = ",".join([t.strip().upper() for t in tickers if t.strip()])
        key = f"brapi:quote:{symbols}:{range_}:{interval}"
        cached = cache.get(key)
        if cached:
            return cached
        data = get_json(f"{self.base_url}/quote/{symbols}", params=self._params({"range": range_, "interval": interval, "fundamental": "true", "dividends": "true"}), timeout=settings.request_timeout)
        cache.set(key, data, settings.cache_ttl_seconds)
        return data

    def list_assets(self, search: str | None = None):
        key = f"brapi:list:{search or ''}"
        cached = cache.get(key)
        if cached:
            return cached
        params = self._params({})
        if search:
            params["search"] = search
        data = get_json(f"{self.base_url}/quote/list", params=params, timeout=settings.request_timeout)
        cache.set(key, data, settings.cache_ttl_seconds)
        return data
