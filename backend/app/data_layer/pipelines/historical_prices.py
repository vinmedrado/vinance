from __future__ import annotations

from time import sleep

from backend.app.data_layer.providers.yfinance_provider import YFinanceProvider
from backend.app.data_layer.quality.checks import only_critical, validate_price_rows
from backend.app.data_layer.repositories.sqlite_repository import (
    connect,
    ensure_patch6_schema,
    fetch_assets,
    finish_log,
    get_last_price_date,
    insert_price_rows,
    start_log,
    write_sync_log,
)
from backend.app.data_layer.utils.date_utils import DEFAULT_START_DATE, next_day_iso, today_iso
from backend.app.data_layer.pipelines.logging_utils import EntityResult, PipelineSummary
from backend.app.data_layer.pipelines.options import PipelineOptions, apply_limit, build_options


RETRY_ATTEMPTS = 2


def _selected_assets(conn, options: PipelineOptions):
    wanted = {"ACAO", "EQUITY", "FII", "ETF", "BDR", "CRIPTO", "CRYPTO"}
    requested_class = options.normalized_asset_class()
    assets = [asset for asset in fetch_assets(conn) if str(asset["asset_class"]).upper() in wanted]

    if requested_class:
        aliases = {
            "acao": {"acao", "equity"},
            "acoes": {"acao", "equity"},
            "equity": {"acao", "equity"},
            "cripto": {"cripto", "crypto"},
            "crypto": {"cripto", "crypto"},
        }
        allowed = aliases.get(requested_class, {requested_class})
        assets = [asset for asset in assets if str(asset["asset_class"]).strip().lower() in allowed]

    tickers = options.normalized_tickers()
    if tickers:
        assets = [asset for asset in assets if asset["ticker"].upper() in tickers]
    return apply_limit(assets, options.limit)


def run(
    incremental: bool = False,
    limit: int | None = None,
    tickers: str | list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    dry_run: bool = False,
    asset_class: str | None = None,
) -> dict:
    options = build_options(limit, tickers, start_date, end_date, dry_run, incremental, asset_class=asset_class)
    provider = YFinanceProvider()
    pipeline_name = "sync_historical_prices_incremental" if options.incremental else "sync_historical_prices_full"
    summary = PipelineSummary(pipeline_name=pipeline_name, dry_run=options.dry_run)

    with connect() as conn:
        ensure_patch6_schema(conn)
        assets = _selected_assets(conn, options)
        print(f"[sync_historical_prices] total de ativos carregados: {len(assets)} | asset_class={asset_class or 'all'} | incremental={options.incremental} | dry_run={options.dry_run}")
        parent_log_id = None if options.dry_run else start_log(conn, pipeline_name, provider.source, "asset_prices")
        try:
            for asset in assets:
                ticker = asset["ticker"]
                start = options.start_date or DEFAULT_START_DATE
                if options.incremental and not options.start_date:
                    start = next_day_iso(get_last_price_date(conn, asset["id"], provider.source), DEFAULT_START_DATE)
                    if start > today_iso():
                        result = EntityResult(ticker, "skipped", rows_skipped=1)
                        summary.add(result)
                        if not options.dry_run:
                            write_sync_log(conn, pipeline_name, provider.source, ticker, "SKIPPED", rows_skipped=1, message="Sem dados novos.")
                        continue
                try:
                    rows = []
                    last_error: Exception | None = None
                    for attempt in range(1, RETRY_ATTEMPTS + 1):
                        try:
                            rows = provider.get_history(ticker, asset["asset_class"], start=start, end=options.end_date)
                            last_error = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_error = exc
                            if attempt < RETRY_ATTEMPTS:
                                sleep(1)
                    if last_error:
                        raise last_error

                    validation_errors = only_critical(validate_price_rows(rows))
                    if validation_errors:
                        message = "; ".join(validation_errors[:3])
                        result = EntityResult(ticker, "skipped", rows_skipped=1, error=message)
                        summary.add(result)
                        if not options.dry_run:
                            write_sync_log(conn, pipeline_name, provider.source, ticker, "SKIPPED", rows_skipped=1, error_message=message)
                        continue
                    inserted = 0 if options.dry_run else insert_price_rows(conn, asset, rows)
                    result = EntityResult(ticker, "success", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted))
                    summary.add(result)
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, ticker, "SUCCESS", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted))
                except Exception as exc:  # noqa: BLE001
                    result = EntityResult(ticker, "failed", rows_skipped=1, error=str(exc))
                    summary.add(result)
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, ticker, "FAILED", rows_skipped=1, error_message=str(exc))
                    continue

            result_dict = summary.as_dict()
            result_dict["total_assets_loaded"] = len(assets)
            result_dict["asset_class_filter"] = asset_class or "all"
            if parent_log_id is not None:
                finish_log(
                    conn,
                    parent_log_id,
                    summary.status(),
                    summary.rows_inserted,
                    summary.rows_updated,
                    summary.rows_skipped,
                    message="Execução finalizada.",
                    error_message="; ".join(summary.errors()[:10]) or None,
                )
            return result_dict
        except Exception as exc:
            if parent_log_id is not None:
                finish_log(conn, parent_log_id, "ERROR", summary.rows_inserted, summary.rows_updated, summary.rows_skipped, error_message=str(exc))
            raise
