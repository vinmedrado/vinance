from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.market.models import Asset, AssetPrice, MacroIndicator
from backend.app.investment.models import AssetDividend, DataSyncLog, FixedIncomeProduct
from backend.app.investment.data_sources.yfinance_provider import YFinanceProvider
from backend.app.investment.data_sources.bcb_provider import BCBProvider
from backend.app.investment.data_sources.tesouro_provider import TesouroProvider


class DataSyncService:
    def __init__(self, db: Session):
        self.db = db

    def _start_log(self, source: str, entity: str, payload: dict[str, Any] | None = None) -> DataSyncLog:
        log = DataSyncLog(source=source, entity=entity, status="running", payload_json=payload or {})
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def _finish_log(self, log: DataSyncLog, *, status: str, inserted: int = 0, updated: int = 0, skipped: int = 0, message: str | None = None) -> None:
        log.status = status
        log.finished_at = datetime.now(timezone.utc)
        log.rows_inserted = inserted
        log.rows_updated = updated
        log.rows_skipped = skipped
        log.message = message
        self.db.commit()

    def get_or_create_asset(self, symbol: str, asset_class: str, *, name: str | None = None, currency: str = "BRL", country: str | None = "BR", source: str = "manual", metadata: dict[str, Any] | None = None) -> Asset:
        symbol = symbol.upper().strip()
        asset_class = asset_class.lower().strip()
        asset = self.db.query(Asset).filter(Asset.symbol == symbol, Asset.asset_class == asset_class).first()
        if asset is None:
            asset = Asset(symbol=symbol, asset_class=asset_class, name=name or symbol, currency=currency, country=country, source=source, metadata_json=metadata or {}, last_updated_at=datetime.now(timezone.utc))
            self.db.add(asset)
            self.db.commit()
            self.db.refresh(asset)
        else:
            asset.name = name or asset.name
            asset.currency = currency or asset.currency
            asset.country = country or asset.country
            asset.source = source or asset.source
            asset.metadata_json = {**(asset.metadata_json or {}), **(metadata or {})}
            asset.last_updated_at = datetime.now(timezone.utc)
            self.db.commit()
        return asset

    def sync_yfinance(self, symbols: list[str], asset_class: str, start: date | None = None, end: date | None = None) -> dict[str, Any]:
        provider = YFinanceProvider()
        log = self._start_log(provider.source, f"{asset_class}:{','.join(symbols)}", {"symbols": symbols, "asset_class": asset_class, "start": str(start) if start else None, "end": str(end) if end else None})
        inserted = skipped = 0
        warnings: list[str] = []
        try:
            for symbol in symbols:
                series = provider.fetch_history(symbol, start=start, end=end)
                warnings.extend([f"{symbol}: {w}" for w in series.warnings])
                asset = self.get_or_create_asset(symbol, asset_class, name=series.metadata.get("longName") or series.metadata.get("shortName") or symbol, currency=series.metadata.get("currency") or "BRL", country=series.metadata.get("country") or "BR", source=provider.source, metadata=series.metadata)
                existing_dates = {row.date.date() for row in self.db.query(AssetPrice.date).filter(AssetPrice.symbol == asset.symbol, AssetPrice.source == provider.source).all() if row.date}
                for row in series.prices:
                    row_date = row["date"].date()
                    if row_date in existing_dates:
                        skipped += 1
                        continue
                    self.db.add(AssetPrice(asset_id=asset.id, symbol=asset.symbol, date=row["date"], close=row["close"], volume=row["volume"], source=provider.source, raw_json=row.get("raw") or {}))
                    inserted += 1
                existing_divs = {(row.date.date(), round(float(row.amount or 0), 8)) for row in self.db.query(AssetDividend).filter(AssetDividend.symbol == asset.symbol, AssetDividend.source == provider.source).all()}
                for div in series.dividends:
                    key = (div["date"].date(), round(float(div["amount"]), 8))
                    if key in existing_divs:
                        skipped += 1
                        continue
                    self.db.add(AssetDividend(asset_id=asset.id, symbol=asset.symbol, date=div["date"], amount=div["amount"], currency=asset.currency, source=provider.source, raw_json=div.get("raw") or {}))
                    inserted += 1
            self.db.commit()
            self._finish_log(log, status="success", inserted=inserted, skipped=skipped, message="; ".join(warnings[:10]) if warnings else "Sincronização concluída com dados reais disponíveis.")
        except Exception as exc:
            self.db.rollback()
            self._finish_log(log, status="error", inserted=inserted, skipped=skipped, message=str(exc))
            raise
        return {"status": log.status, "inserted": inserted, "skipped": skipped, "warnings": warnings}

    def sync_bcb_selic(self, start: date | None = None, end: date | None = None) -> dict[str, Any]:
        provider = BCBProvider()
        log = self._start_log(provider.source, "selic", {"start": str(start) if start else None, "end": str(end) if end else None})
        inserted = skipped = 0
        try:
            rows = provider.fetch_series(11, start=start, end=end)
            existing = {row.date.date() for row in self.db.query(MacroIndicator.date).filter(MacroIndicator.code == "selic", MacroIndicator.source == provider.source).all() if row.date}
            for row in rows:
                if row["date"].date() in existing:
                    skipped += 1
                    continue
                self.db.add(MacroIndicator(code="selic", name="Taxa Selic", date=row["date"], value=row["value"], source=provider.source, raw_json=row.get("raw") or {}))
                inserted += 1
            self.db.commit()
            self._finish_log(log, status="success", inserted=inserted, skipped=skipped, message="Selic sincronizada via Banco Central.")
        except Exception as exc:
            self.db.rollback(); self._finish_log(log, status="error", inserted=inserted, skipped=skipped, message=str(exc)); raise
        return {"status": log.status, "inserted": inserted, "skipped": skipped}

    def sync_tesouro(self) -> dict[str, Any]:
        provider = TesouroProvider()
        log = self._start_log(provider.source, "tesouro_direto")
        inserted = updated = 0
        try:
            for item in provider.fetch_bonds():
                row = self.db.query(FixedIncomeProduct).filter(FixedIncomeProduct.user_id.is_(None), FixedIncomeProduct.issuer == item["issuer"], FixedIncomeProduct.product_type == item["product_type"], FixedIncomeProduct.name == item["name"], FixedIncomeProduct.maturity_date == item.get("maturity_date")).first()
                if row is None:
                    row = FixedIncomeProduct(**{k: v for k, v in item.items() if k != "raw"}, raw_json=item.get("raw") or {})
                    self.db.add(row); inserted += 1
                else:
                    row.rate = item["rate"]; row.minimum_investment = item["minimum_investment"]; row.raw_json = item.get("raw") or {}; updated += 1
            self.db.commit(); self._finish_log(log, status="success", inserted=inserted, updated=updated, message="Tesouro Direto sincronizado.")
        except Exception as exc:
            self.db.rollback(); self._finish_log(log, status="error", inserted=inserted, updated=updated, message=str(exc)); raise
        return {"status": log.status, "inserted": inserted, "updated": updated}
