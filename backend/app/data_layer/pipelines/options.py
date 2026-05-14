from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class PipelineOptions:
    limit: int | None = None
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    dry_run: bool = False
    incremental: bool = False
    asset_class: str | None = None

    def normalized_asset_class(self) -> str | None:
        if not self.asset_class or str(self.asset_class).lower() in {"all", "*"}:
            return None
        return str(self.asset_class).strip().lower()

    def normalized_tickers(self) -> set[str] | None:
        if not self.tickers:
            return None
        return {item.strip().upper() for item in self.tickers if item and item.strip()}


def parse_tickers(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip().upper() for item in value.split(',') if item.strip()]


def validate_iso_date(value: str | None, field_name: str) -> str | None:
    if not value:
        return None
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError(f'{field_name} deve estar no formato YYYY-MM-DD: {value}') from exc
    return value


def apply_limit(items: Iterable, limit: int | None) -> list:
    data = list(items)
    if limit is None or limit <= 0:
        return data
    return data[:limit]


def build_options(
    limit: int | None = None,
    tickers: str | list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    dry_run: bool = False,
    incremental: bool = False,
    asset_class: str | None = None,
) -> PipelineOptions:
    parsed_tickers = parse_tickers(tickers) if isinstance(tickers, str) else tickers
    return PipelineOptions(
        limit=limit,
        tickers=parsed_tickers,
        start_date=validate_iso_date(start_date, 'start-date'),
        end_date=validate_iso_date(end_date, 'end-date'),
        dry_run=dry_run,
        incremental=incremental,
        asset_class=asset_class,
    )
