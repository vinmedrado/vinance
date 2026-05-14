from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.finance_math import correlation, max_drawdown, pct_return, safe_round, volatility
from backend.app.market.models import Asset, AssetPrice, MacroIndicator, MarketIndex
from backend.app.investment.models import AssetDividend, DataSyncLog


class MarketDataService:
    def __init__(self, db: Session):
        self.db = db


    def get_assets(self, search: str | None = None) -> list[dict[str, Any]]:
        query = self.db.query(Asset).order_by(Asset.symbol.asc())
        if search:
            like = f"%{search}%"
            query = query.filter((Asset.symbol.ilike(like)) | (Asset.name.ilike(like)))
        return [{"symbol": a.symbol, "name": a.name, "asset_class": a.asset_class, "currency": a.currency, "source": a.source} for a in query.limit(200).all()]

    def get_b3_quotes(self, tickers: list[str]) -> list[dict[str, Any]]:
        results = []
        for ticker in tickers:
            row = self.db.query(AssetPrice).filter(AssetPrice.symbol == ticker).order_by(AssetPrice.date.desc()).first()
            results.append({"symbol": ticker, "close": row.close if row else None, "date": row.date.isoformat() if row and row.date else None, "source": row.source if row else None})
        return results

    def get_macro_context(self) -> dict[str, Any]:
        return self.macro_context()

    def dashboard(self) -> dict[str, Any]:
        total_assets = self.db.query(func.count(Asset.id)).scalar() or 0
        by_class_rows = self.db.query(Asset.asset_class, func.count(Asset.id)).group_by(Asset.asset_class).all()
        coverage_rows = (
            self.db.query(AssetPrice.symbol, func.min(AssetPrice.date), func.max(AssetPrice.date), func.count(AssetPrice.id))
            .group_by(AssetPrice.symbol)
            .all()
        )
        latest_logs = self.db.query(DataSyncLog).order_by(DataSyncLog.started_at.desc()).limit(20).all()
        return {
            "total_assets": total_assets,
            "asset_counts_by_class": {cls: count for cls, count in by_class_rows},
            "historical_coverage": [
                {
                    "symbol": symbol,
                    "start": start.isoformat() if start else None,
                    "end": end.isoformat() if end else None,
                    "rows": rows,
                }
                for symbol, start, end, rows in coverage_rows
            ],
            "latest_sync_logs": [
                {
                    "source": row.source,
                    "entity": row.entity,
                    "status": row.status,
                    "rows_inserted": row.rows_inserted,
                    "rows_updated": row.rows_updated,
                    "rows_skipped": row.rows_skipped,
                    "message": row.message,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                }
                for row in latest_logs
            ],
        }

    def metrics_for_asset_class(self, asset_class: str, limit: int = 200) -> dict[str, Any]:
        cls = asset_class.strip().lower()
        aliases = {cls, cls.rstrip("s")}
        assets = self.db.query(Asset).filter(Asset.asset_class.in_(aliases)).limit(limit).all()
        analyses = []
        for asset in assets:
            prices = [r.close for r in self.db.query(AssetPrice).filter(AssetPrice.symbol == asset.symbol).order_by(AssetPrice.date.asc()).all()]
            dividends = [r.amount for r in self.db.query(AssetDividend).filter(AssetDividend.symbol == asset.symbol).order_by(AssetDividend.date.asc()).all()]
            annual_div = sum(dividends[-12:]) if dividends else 0.0
            last = next((p for p in reversed(prices) if p and p > 0), None)
            analyses.append({
                "symbol": asset.symbol,
                "asset_class": asset.asset_class,
                "return_5y_or_available": safe_round(pct_return(prices)),
                "volatility": safe_round(volatility(prices)),
                "max_drawdown": safe_round(max_drawdown(prices)),
                "dividend_yield_estimated": safe_round(annual_div / last if last else None),
                "liquidity_proxy_volume_last": self._last_volume(asset.symbol),
            })
        return {"asset_class": cls, "comparison_rule": "Métricas e ordenações devem ser usadas apenas dentro desta classe.", "assets": analyses}

    def macro_context(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for code in ("SELIC", "CDI", "IPCA", "USD_BRL"):
            row = self.db.query(MacroIndicator).filter(MacroIndicator.code == code).order_by(MacroIndicator.date.desc()).first()
            if row:
                result[code] = {"value": row.value, "date": row.date.isoformat() if row.date else None, "source": row.source}
        return result

    def market_context_for_decision(self) -> dict[str, Any]:
        macro = self.macro_context()
        stress = 0.0
        selic = (macro.get("SELIC") or {}).get("value")
        ipca = (macro.get("IPCA") or {}).get("value")
        if selic and selic >= 10:
            stress += 0.20
        if ipca and ipca >= 0.6:
            stress += 0.20
        return {"macro": macro, "macro_stress": min(stress, 1.0)}

    def _last_volume(self, symbol: str) -> float | None:
        row = self.db.query(AssetPrice).filter(AssetPrice.symbol == symbol).order_by(AssetPrice.date.desc()).first()
        return row.volume if row else None
