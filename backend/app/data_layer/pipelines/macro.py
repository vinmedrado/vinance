from __future__ import annotations

from datetime import datetime
from time import sleep

from backend.app.data_layer.catalog import BCB_SGS_INDICATORS
from backend.app.data_layer.providers.bcb_sgs_provider import BcbSgsProvider
from backend.app.data_layer.quality.checks import only_critical, validate_macro_rows
from backend.app.data_layer.repositories.sqlite_repository import connect, ensure_patch6_schema, finish_log, insert_macro_rows, start_log, write_sync_log
from backend.app.data_layer.pipelines.logging_utils import EntityResult, PipelineSummary
from backend.app.data_layer.pipelines.options import PipelineOptions, apply_limit, build_options

RETRY_ATTEMPTS = 2


def _br_date(value: str | None, default: str | None = None) -> str | None:
    if not value:
        return default
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")


def _selected_indicators(options: PipelineOptions):
    items = list(BCB_SGS_INDICATORS.items())
    tickers = options.normalized_tickers()
    if tickers:
        items = [(key, cfg) for key, cfg in items if key.upper() in tickers or cfg["name"].upper() in tickers or str(cfg["code"]).upper() in tickers]
    return apply_limit(items, options.limit)


def run(limit: int | None = None, tickers: str | list[str] | None = None, start_date: str | None = None, end_date: str | None = None, dry_run: bool = False) -> dict:
    options = build_options(limit, tickers, start_date, end_date, dry_run, False)
    provider = BcbSgsProvider()
    pipeline_name = "sync_macro_indicators"
    summary = PipelineSummary(pipeline_name=pipeline_name, dry_run=options.dry_run)
    with connect() as conn:
        ensure_patch6_schema(conn)
        items = _selected_indicators(options)
        parent_log_id = None if options.dry_run else start_log(conn, pipeline_name, provider.source, "macro_indicators")
        try:
            for key, cfg in items:
                entity = cfg["name"]
                try:
                    rows = []
                    last_error: Exception | None = None
                    for attempt in range(1, RETRY_ATTEMPTS + 1):
                        try:
                            rows = provider.get_series(cfg["code"], cfg["name"], start=_br_date(options.start_date, "01/01/2015"), end=_br_date(options.end_date))
                            last_error = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_error = exc
                            if attempt < RETRY_ATTEMPTS:
                                sleep(1)
                    if last_error:
                        raise last_error
                    validation_errors = only_critical(validate_macro_rows(rows))
                    if validation_errors:
                        message = "; ".join(validation_errors[:3])
                        summary.add(EntityResult(entity, "skipped", rows_skipped=1, error=message))
                        if not options.dry_run:
                            write_sync_log(conn, pipeline_name, provider.source, entity, "SKIPPED", rows_skipped=1, error_message=message)
                        continue
                    inserted = 0 if options.dry_run else insert_macro_rows(conn, rows)
                    summary.add(EntityResult(entity, "success", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted)))
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, entity, "SUCCESS", rows_inserted=inserted, rows_skipped=max(0, len(rows) - inserted), payload={"key": key, "code": cfg["code"]})
                except Exception as exc:  # noqa: BLE001
                    summary.add(EntityResult(entity, "failed", rows_skipped=1, error=str(exc)))
                    if not options.dry_run:
                        write_sync_log(conn, pipeline_name, provider.source, entity, "FAILED", rows_skipped=1, error_message=str(exc), payload={"key": key, "code": cfg["code"]})
                    continue
            result = summary.as_dict()
            if parent_log_id is not None:
                finish_log(conn, parent_log_id, summary.status(), summary.rows_inserted, summary.rows_updated, summary.rows_skipped, message="Execução finalizada.", error_message="; ".join(summary.errors()[:10]) or None)
            return result
        except Exception as exc:
            if parent_log_id is not None:
                finish_log(conn, parent_log_id, "ERROR", summary.rows_inserted, summary.rows_updated, summary.rows_skipped, error_message=str(exc))
            raise
