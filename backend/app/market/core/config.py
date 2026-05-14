import os
from dataclasses import dataclass

@dataclass(frozen=True)
class MarketSettings:
    brapi_base_url: str = os.getenv("BRAPI_BASE_URL", "https://brapi.dev/api")
    brapi_token: str | None = os.getenv("BRAPI_TOKEN") or None
    coingecko_base_url: str = os.getenv("COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3")
    coingecko_api_key: str | None = os.getenv("COINGECKO_API_KEY") or None
    bcb_base_url: str = os.getenv("BCB_BASE_URL", "https://api.bcb.gov.br/dados/serie/bcdata.sgs")
    request_timeout: float = float(os.getenv("MARKET_REQUEST_TIMEOUT", "15"))
    cache_ttl_seconds: int = int(os.getenv("MARKET_CACHE_TTL_SECONDS", "900"))
    default_symbols: str = os.getenv("MARKET_DEFAULT_SYMBOLS", "PETR4,VALE3,ITUB4,BBAS3,BOVA11,IVVB11,HGLG11,KNRI11,AAPL34,MSFT34")
    default_crypto_ids: str = os.getenv("MARKET_DEFAULT_CRYPTO_IDS", "bitcoin,ethereum,solana")

settings = MarketSettings()
