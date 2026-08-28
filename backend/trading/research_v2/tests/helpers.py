from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def report_bundle(root: Path, run_id: str = "backtest-run", *, timestamp: str = "2026-07-14T12:00:00+00:00") -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    pnls = [2.0, 1.5, -1.0, 2.2, -0.8, 1.8, 2.4, -1.2, 1.7, 2.1] * 4
    trades = []
    equity = 10_000.0
    equity_curve = []
    drawdown_curve = []
    peak = equity
    for index, pnl in enumerate(pnls):
        entry = start + timedelta(hours=index)
        exit_time = entry + timedelta(minutes=30)
        trades.append(
            {
                "position_id": f"p{index}",
                "prediction_id": f"x{index}",
                "symbol": "BTCUSDT",
                "interval": "5m",
                "entry_price": 100.0,
                "exit_price": 101.0,
                "quantity": 1.0,
                "entry_time": entry.isoformat(),
                "exit_time": exit_time.isoformat(),
                "exit_reason": "TAKE_PROFIT" if pnl > 0 else "STOP_LOSS",
                "gross_pnl": pnl + 0.2,
                "fees": 0.2,
                "net_pnl": pnl,
                "return_pct": pnl / 100,
                "holding_candles": index % 24 + 1,
            }
        )
        equity += pnl
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        point = {"timestamp": exit_time.isoformat(), "equity": equity, "drawdown": dd, "invested_capital": 0.0}
        equity_curve.append(point)
        drawdown_curve.append({"timestamp": exit_time.isoformat(), "equity": equity, "drawdown": dd})

    threshold_rows_1 = _threshold_rows(1.0)
    threshold_rows_2 = _threshold_rows(0.8)
    windows = [
        _window(1, threshold_rows_1, net_test=12.0, test_trades=15),
        _window(2, threshold_rows_2, net_test=8.0, test_trades=15),
    ]
    summary = {
        "capital_initial": 10_000.0,
        "capital_final": equity,
        "net_profit": sum(pnls),
        "profit_factor": 4.0,
        "expectancy": sum(pnls) / len(pnls),
        "max_drawdown": max(row["drawdown"] for row in equity_curve),
        "total_fees": 8.0,
        "total_slippage": 4.0,
        "total_spread": 2.0,
        "number_of_trades": len(trades),
    }
    metadata = {
        "run_id": run_id,
        "engine_version": "v2",
        "timestamp": timestamp,
        "symbol": "BTCUSDT",
        "interval": "5m",
        "target_name": "v2_long_tp_100bps_sl_50bps_h_24",
        "model_name": "synthetic",
        "thresholds": {"take_profit": 0.6, "stop_loss": 0.6},
        "costs": {"fee_bps": 10.0, "slippage_bps": 5.0, "spread_bps": 2.0},
        "risk": {"fixed_fraction": 0.02, "min_confidence": 0.6},
        "temporal_integrity_valid": True,
    }
    payloads = {
        "backtest_summary": summary,
        "trades": trades,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "daily_results": [{"date": "2026-01-01", "net_pnl": sum(pnls), "return": sum(pnls) / 10_000}],
        "monthly_results": [{"month": "2026-01", "net_pnl": sum(pnls), "return": sum(pnls) / 10_000}],
        "signal_analysis": {
            "by_confidence": {"0.55-0.70": 20, "0.70-0.85": 20},
            "by_volatility_regime": {},
        },
        "threshold_comparison": [],
        "baseline_comparison": [],
        "walk_forward_results": {
            "configuration": {"model_frozen": True},
            "windows": windows,
            "consolidated": {
                "total_windows": 2,
                "positive_test_windows": 2,
                "negative_test_windows": 0,
                "neutral_test_windows": 0,
                "aggregate_test_trades": 30,
                "aggregate_test_net_profit": 20.0,
                "aggregate_test_profit_factor": 2.0,
                "aggregate_test_expectancy": 20 / 30,
                "aggregate_test_max_drawdown": 0.02,
                "out_of_sample_positive": True,
            },
        },
        "run_metadata": metadata,
    }
    for name, payload in payloads.items():
        (run_dir / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    return run_dir


def _threshold_rows(scale: float) -> list[dict]:
    return [
        _threshold(0.50, 0.50, 20, 12 * scale, 2.2, 0.60, 0.20, 0.01),
        _threshold(0.60, 0.50, 15, 14 * scale, 2.8, 0.90 * scale, 0.24, 0.018),
        _threshold(0.50, 0.60, 12, 2 * scale, 1.1, 0.10, 0.02, 0.025),
        _threshold(0.60, 0.60, 10, -2 * scale, 0.8, -0.20, -0.03, 0.04),
    ]


def _threshold(tp, sl, trades, net, pf, expectancy, sharpe, drawdown) -> dict:
    return {
        "threshold_tp": tp,
        "threshold_sl": sl,
        "trades": trades,
        "net_profit": net,
        "profit_factor": pf,
        "win_rate": 0.6,
        "expectancy": expectancy,
        "sharpe": sharpe,
        "max_drawdown": drawdown,
    }


def _window(window_id: int, rows: list[dict], *, net_test: float, test_trades: int) -> dict:
    return {
        "window_id": window_id,
        "validation_threshold_results": rows,
        "threshold_tp_selected": 0.5,
        "threshold_sl_selected": 0.5,
        "trades_test": test_trades,
        "net_profit_test": net_test,
        "profit_factor_test": 2.0,
        "expectancy_test": net_test / test_trades,
        "max_drawdown_test": 0.02,
    }
