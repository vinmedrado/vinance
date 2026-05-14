from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

try:
    import yfinance as yf
except Exception:  # noqa: BLE001
    yf = None


@dataclass
class DiscoveryResult:
    status: str
    source: str
    name: str | None = None
    notes: str | None = None
    records: int = 0


class AssetDiscoveryService:
    """Valida símbolos com prioridade de fontes e fallback gratuito sem derrubar o pipeline."""

    def source_priority_for(self, asset_class: str, explicit: str | None = None) -> list[str]:
        if explicit:
            return [s.strip().lower() for s in explicit.split(',') if s.strip()]
        cls = (asset_class or '').lower()
        if cls == 'crypto':
            return ['coingecko', 'yfinance']
        if cls in {'equity', 'fii', 'etf', 'bdr', 'index', 'currency', 'commodity'}:
            return ['yfinance', 'stooq']
        return ['yfinance']

    def validate_yahoo_symbol(self, yahoo_symbol: str) -> DiscoveryResult:
        if not yahoo_symbol:
            return DiscoveryResult(status='unsupported', source='yfinance', notes='Símbolo Yahoo vazio.')
        if yf is None:
            return DiscoveryResult(status='error', source='yfinance', notes='yfinance não disponível.')
        try:
            ticker = yf.Ticker(yahoo_symbol)
            hist = ticker.history(period='1y', auto_adjust=False)
            records = 0 if hist is None else len(hist)
            if hist is not None and not hist.empty:
                status = 'active' if records >= 100 else 'weak_data'
                return DiscoveryResult(status=status, source='yfinance', name=None, records=records, notes=f'Yahoo Finance retornou {records} registros.')
            return DiscoveryResult(status='not_found', source='yfinance', notes='Yahoo Finance não retornou histórico.')
        except Exception as exc:  # noqa: BLE001
            return DiscoveryResult(status='error', source='yfinance', notes=f'Erro yfinance: {exc}')

    def validate_stooq_symbol(self, ticker: str, yahoo_symbol: str | None = None) -> DiscoveryResult:
        # Fallback leve: Stooq cobre parte limitada do universo B3 e varia formato. Não força erro fatal.
        symbol = (ticker or yahoo_symbol or '').replace('.SA', '').lower()
        if not symbol:
            return DiscoveryResult(status='unsupported', source='stooq', notes='Símbolo vazio para Stooq.')
        candidates = [f'{symbol}.br', symbol]
        for cand in candidates:
            try:
                url = f'https://stooq.com/q/l/?s={cand}&f=sd2t2ohlcv&h&e=csv'
                response = requests.get(url, timeout=10)
                if response.status_code != 200 or 'No data' in response.text:
                    continue
                lines = [ln for ln in response.text.splitlines() if ln.strip()]
                if len(lines) >= 2 and 'N/D' not in lines[-1]:
                    return DiscoveryResult(status='active', source='stooq', records=len(lines)-1, notes=f'Stooq retornou dados para {cand}.')
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                continue
        return DiscoveryResult(status='not_found', source='stooq', notes='Stooq não retornou dados para os formatos testados.')

    def validate_crypto_coingecko(self, ticker: str) -> DiscoveryResult:
        symbol = (ticker or '').lower().replace('-usd', '')
        if not symbol:
            return DiscoveryResult(status='unsupported', source='coingecko', notes='Ticker cripto vazio.')
        try:
            url = 'https://api.coingecko.com/api/v3/search'
            response = requests.get(url, params={'query': symbol}, timeout=12)
            if response.status_code != 200:
                return DiscoveryResult(status='error', source='coingecko', notes=f'HTTP {response.status_code}')
            data: dict[str, Any] = response.json()
            coins = data.get('coins') or []
            matched = [c for c in coins if str(c.get('symbol', '')).lower() == symbol]
            if matched:
                coin = matched[0]
                return DiscoveryResult(status='active', source='coingecko', name=coin.get('name'), notes=f"CoinGecko id={coin.get('id')}")
            return DiscoveryResult(status='not_found', source='coingecko', notes='Cripto não encontrada no CoinGecko.')
        except Exception as exc:  # noqa: BLE001
            return DiscoveryResult(status='error', source='coingecko', notes=f'Erro CoinGecko: {exc}')

    def validate(self, ticker: str, yahoo_symbol: str, asset_class: str, source_priority: str | None = None) -> DiscoveryResult:
        notes = []
        for source in self.source_priority_for(asset_class, source_priority):
            if source == 'coingecko':
                result = self.validate_crypto_coingecko(ticker)
            elif source == 'stooq':
                result = self.validate_stooq_symbol(ticker, yahoo_symbol)
            elif source == 'yfinance':
                result = self.validate_yahoo_symbol(yahoo_symbol)
            else:
                result = DiscoveryResult(status='unsupported', source=source, notes=f'Fonte não suportada: {source}')
            notes.append(f'{result.source}:{result.status} {result.notes or ""}'.strip())
            if result.status in {'active', 'weak_data'}:
                result.notes = ' | '.join(notes)
                return result
            # not_found/unsupported in primary can try fallback; technical error also tries next source.
        final_status = 'not_found' if any(n.startswith(('yfinance:not_found', 'coingecko:not_found', 'stooq:not_found')) for n in notes) else 'error'
        return DiscoveryResult(status=final_status, source='fallback_exhausted', notes=' | '.join(notes))

    def fetch_top_crypto(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            url = 'https://api.coingecko.com/api/v3/coins/markets'
            response = requests.get(
                url,
                params={'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': max(1, min(int(limit), 250)), 'page': 1},
                timeout=20,
            )
            response.raise_for_status()
            rows = []
            for item in response.json():
                symbol = str(item.get('symbol') or '').upper()
                if not symbol:
                    continue
                rows.append({
                    'ticker': symbol,
                    'yahoo_symbol': f'{symbol}-USD',
                    'name': item.get('name') or symbol,
                    'asset_class': 'crypto',
                    'market': 'global',
                    'currency': 'USD',
                    'source': 'crypto_api',
                    'api_status': 'active',
                    'preferred_source': 'coingecko',
                    'last_source_used': 'coingecko',
                    'source_priority': 'coingecko,yfinance',
                    'notes': f"coingecko_id={item.get('id')}; market_cap_rank={item.get('market_cap_rank')}",
                })
            return rows
        except Exception:
            fallback = [
                ('BTC', 'Bitcoin'), ('ETH', 'Ethereum'), ('SOL', 'Solana'), ('BNB', 'BNB'), ('XRP', 'XRP'),
                ('ADA', 'Cardano'), ('DOGE', 'Dogecoin'), ('AVAX', 'Avalanche'), ('LINK', 'Chainlink'), ('DOT', 'Polkadot'),
                ('TRX', 'TRON'), ('MATIC', 'Polygon'), ('LTC', 'Litecoin'), ('BCH', 'Bitcoin Cash'), ('UNI', 'Uniswap'),
            ]
            return [
                {'ticker': t, 'yahoo_symbol': f'{t}-USD', 'name': n, 'asset_class': 'crypto', 'market': 'global', 'currency': 'USD', 'source': 'crypto_api_fallback', 'api_status': 'pending_validation', 'preferred_source': 'coingecko', 'source_priority': 'coingecko,yfinance'}
                for t, n in fallback[:limit]
            ]
