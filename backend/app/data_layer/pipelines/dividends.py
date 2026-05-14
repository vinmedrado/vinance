from __future__ import annotations

from time import sleep

from backend.app.data_layer.providers.yfinance_provider import YFinanceProvider
from backend.app.data_layer.repositories.sqlite_repository import connect, ensure_patch6_schema, fetch_assets, finish_log, insert_dividend_rows, start_log, write_sync_log
from backend.app.data_layer.pipelines.logging_utils import EntityResult, PipelineSummary
from backend.app.data_layer.pipelines.options import PipelineOptions, apply_limit, build_options

RETRY_ATTEMPTS = 2


def _selected_assets(conn, options: PipelineOptions):
    wanted = {"ACAO", "EQUITY", "FII", "ETF", "BDR"}
    assets = [asset for asset in fetch_assets(conn) if str(asset["asset_class"]).upper() in wanted]
    tickers = options.normalized_tickers()
    if tickers:
        assets = [asset for asset in assets if asset["ticker"].upper() in tickers]
    return apply_limit(assets, options.limit)


def run(limit: int | None = None, tickers: str | list[str] | None = None, start_date: str | None = None, end_date: str | None = None, dry_run: bool = False) -> dict:
    options = build_options(limit, tickers, start_date, end_date, dry_run, False)
    provider = YFinanceProvider()
    pipeline_name = "sync_dividends"
    summary = PipelineSummary(pipeline_name=pipeline_name, dry_run=options.dry_run)
    with connect() as conn:
        ensure_patch6_schema(conn)
        assets = _selected_assets(conn, options)
        parent_log_id = None if options.dry_run else start_log(conn, pipeline_name, provider.source, "asset_dividends")
        try:
            for asset in assets:
                ticker = asset["ticker"]
                try:
                    rows = []
                    last_error: Exception | None = None
                    for attempt in range(1, RETRY_ATTEMPTS + 1):
                        try:
                            rows = provider.get_dividends(ticker, asset["asset_class"])
                            last_error = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_error = exc
                            if attempt < RETRY_ATTEMPTS:
                                sleep(1)
                    if last_error:
                        raise last_error
                    if options.start_date:
                        rows = [row for row in rows if row["date"] >= options.start_date]
                    if options.end_date:
                        rows = [row for row in rows if row["date"] <= options.end_date]
                    if not rows:
                        summary.add(EntityResult(ticker, "skipped", rows_skipped=1))
                        if not options.dry_run:
                            write_sync_log(conn, pipeline_name, provider.source, ticker, "SKIPPED", rows_skipped=1, message="Sem dividendos no período.")
                        continue
                    inserted = 0 if options.dry_run else insert_dividend_rows(conn, asset, rows)
                    summary.add(EntityResult(ticker, "success", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted)))
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, ticker, "SUCCESS", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted))
                except Exception as exc:  # noqa: BLE001
                    summary.add(EntityResult(ticker, "failed", rows_skipped=1, error=str(exc)))
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, ticker, "FAILED", rows_skipped=1, error_message=str(exc))
                    continue
            result = summary.as_dict()
            if parent_log_id is not None:
                finish_log(conn, parent_log_id, summary.status(), summary.rows_inserted, summary.rows_updated, summary.rows_skipped, message="Execução finalizada.", error_message="; ".join(summary.errors()[:10]) or None)
            return result
        except Exception as exc:
            if parent_log_id is not None:
                finish_log(conn, parent_log_id, "ERROR", summary.rows_inserted, summary.rows_updated, summary.rows_skipped, error_message=str(exc))
            raise
