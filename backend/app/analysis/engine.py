from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .analysis_quality import validate_metrics, validate_price_rows, validate_score
from .analysis_repository import ensure_analysis_schema, fetch_assets, fetch_dividends, fetch_prices, get_connection, log_run, save_metrics, save_score
from .liquidity_metrics import calculate_liquidity_metrics
from .ranking_engine import persist_rankings
from .return_metrics import calculate_return_metrics
from .risk_metrics import calculate_risk_metrics
from .scoring_engine import calculate_score
from .valuation_metrics import calculate_dividend_metrics, calculate_trend_metrics

def _row_to_dict(row) -> dict[str, Any]:
    return dict(row)

def run_analysis_engine(asset_class: str = "all", tickers: list[str] | None = None, limit: int | None = None, dry_run: bool = False, top_n: int = 30) -> dict[str, Any]:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    details=[]; score_rows=[]; total_success=total_failed=total_skipped=0
    with get_connection() as conn:
        ensure_analysis_schema(conn)
        assets = fetch_assets(conn, asset_class=asset_class, tickers=tickers, limit=limit)
        for asset in assets:
            ticker = asset["ticker"]
            try:
                prices = [_row_to_dict(r) for r in fetch_prices(conn, asset["id"])]
                ok, message = validate_price_rows(prices)
                if not ok:
                    total_skipped += 1; details.append({"ticker": ticker, "status": "skipped", "reason": message}); continue
                dividends = [_row_to_dict(r) for r in fetch_dividends(conn, asset["id"])]
                metrics = {}
                metrics.update(calculate_return_metrics(prices)); metrics.update(calculate_risk_metrics(prices)); metrics.update(calculate_liquidity_metrics(prices)); metrics.update(calculate_trend_metrics(prices)); metrics.update(calculate_dividend_metrics(prices, dividends))
                issues = validate_metrics(metrics)
                score = calculate_score(asset["asset_class"], metrics)
                issues.extend(validate_score(score))
                status = "warning" if issues else "success"; message = "; ".join(issues) if issues else "ok"
                if not dry_run:
                    save_metrics(conn, asset, metrics, quality_status=status, quality_message=message); save_score(conn, asset, score, calculated_at=started)
                total_success += 1
                row = {"asset_id": asset["id"], "ticker": ticker, "asset_class": asset["asset_class"], **score}
                score_rows.append(row); details.append({"ticker": ticker, "status": status, "score_total": score.get("score_total"), "message": message})
            except Exception as exc:
                total_failed += 1; details.append({"ticker": ticker, "status": "failed", "error": str(exc)})
        if not dry_run:
            persist_rankings(conn, score_rows, top_n=top_n, calculated_at=started)
            log_run(conn, status="success" if total_failed == 0 else "partial_success", started_at=started, total_assets=len(assets), total_success=total_success, total_failed=total_failed, total_skipped=total_skipped, payload={"dry_run": dry_run, "details": details[:200]})
            conn.commit()
    return {"total_assets": len(assets), "total_success": total_success, "total_failed": total_failed, "total_skipped": total_skipped, "dry_run": dry_run, "details": details}
