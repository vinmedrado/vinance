from __future__ import annotations

from time import sleep

from backend.app.data_layer.catalog import MARKET_INDICES
from backend.app.data_layer.providers.yfinance_provider import YFinanceProvider
from backend.app.data_layer.quality.checks import only_critical, validate_price_rows
from backend.app.data_layer.repositories.sqlite_repository import connect, ensure_patch6_schema, finish_log, get_last_index_date, insert_index_rows, start_log, write_sync_log
from backend.app.data_layer.utils.date_utils import DEFAULT_START_DATE, next_day_iso, today_iso
from backend.app.data_layer.pipelines.logging_utils import EntityResult, PipelineSummary
from backend.app.data_layer.pipelines.options import PipelineOptions, apply_limit, build_options

RETRY_ATTEMPTS = 2


def _selected_indices(options: PipelineOptions):
    items = MARKET_INDICES
    tickers = options.normalized_tickers()
    if tickers:
        items = [item for item in items if item["symbol"].upper() in tickers]
    return apply_limit(items, options.limit)


def run(incremental: bool = False, limit: int | None = None, tickers: str | list[str] | None = None, start_date: str | None = None, end_date: str | None = None, dry_run: bool = False) -> dict:
    options = build_options(limit, tickers, start_date, end_date, dry_run, incremental)
    provider = YFinanceProvider()
    pipeline_name = "sync_market_indices_incremental" if options.incremental else "sync_market_indices_full"
    summary = PipelineSummary(pipeline_name=pipeline_name, dry_run=options.dry_run)
    with connect() as conn:
        ensure_patch6_schema(conn)
        items = _selected_indices(options)
        parent_log_id = None if options.dry_run else start_log(conn, pipeline_name, provider.source, "market_indices")
        try:
            for index_cfg in items:
                symbol = index_cfg["symbol"]
                start = options.start_date or DEFAULT_START_DATE
                if options.incremental and not options.start_date:
                    start = next_day_iso(get_last_index_date(conn, symbol, provider.source), DEFAULT_START_DATE)
                    if start > today_iso():
                        summary.add(EntityResult(symbol, "skipped", rows_skipped=1))
                        if not options.dry_run:
                            write_sync_log(conn, pipeline_name, provider.source, symbol, "SKIPPED", rows_skipped=1, message="Sem dados novos.")
                        continue
                try:
                    rows = []
                    last_error: Exception | None = None
                    for attempt in range(1, RETRY_ATTEMPTS + 1):
                        try:
                            rows = provider.get_history(index_cfg["source_symbol"], None, start=start, end=options.end_date)
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
                        summary.add(EntityResult(symbol, "skipped", rows_skipped=1, error=message))
                        if not options.dry_run:
                            write_sync_log(conn, pipeline_name, provider.source, symbol, "SKIPPED", rows_skipped=1, error_message=message)
                        continue
                    inserted = 0 if options.dry_run else insert_index_rows(conn, symbol, index_cfg["name"], rows)
                    summary.add(EntityResult(symbol, "success", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted)))
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, symbol, "SUCCESS", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted))
                except Exception as exc:  # noqa: BLE001
                    summary.add(EntityResult(symbol, "failed", rows_skipped=1, error=str(exc)))
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, symbol, "FAILED", rows_skipped=1, error_message=str(exc))
                    continue
            result = summary.as_dict()
            if parent_log_id is not None:
                finish_log(conn, parent_log_id, summary.status(), summary.rows_inserted, summary.rows_updated, summary.rows_skipped, message="Execução finalizada.", error_message="; ".join(summary.errors()[:10]) or None)
            return result
        except Exception as exc:
            if parent_log_id is not None:
                finish_log(conn, parent_log_id, "ERROR", summary.rows_inserted, summary.rows_updated, summary.rows_skipped, error_message=str(exc))
            raise
