from __future__ import annotations

import json
from pathlib import Path


def validation_fixture(root: Path, cases: list[dict] | None = None) -> dict[str, Path]:
    cases = cases or [
        _case("btc-hgb-1", "BTCUSDT", "target_a", "hist_gradient_boosting", "2026-01-01", "2026-03-01", 20.0),
        _case("btc-rf-2", "BTCUSDT", "target_b", "random_forest", "2026-03-02", "2026-05-01", 12.0),
        _case("eth-hgb-3", "ETHUSDT", "target_a", "hist_gradient_boosting", "2026-01-01", "2026-03-01", -3.0),
    ]
    manifest_path = root / "artifacts" / "manifest.json"
    backtest_root = root / "backtests"
    research_root = root / "research"
    output_root = root / "validation"
    manifest_path.parent.mkdir(parents=True)
    models = []
    for case in cases:
        models.append(
            {
                "symbol": case["symbol"],
                "interval": "5m",
                "target_name": case["target"],
                "model_name": case["model"],
                "artifact_dir": f"artifacts/{case['run_id']}",
                "is_best": True,
            }
        )
        _write_backtest(backtest_root, case)
        _write_research(research_root, case)
    manifest_path.write_text(json.dumps({"generated_at": "2026-07-15T00:00:00+00:00", "models": models}))
    return {
        "manifest": manifest_path,
        "backtests": backtest_root,
        "research": research_root,
        "output": output_root,
    }


def _case(run_id, symbol, target, model, start, end, oos_net) -> dict:
    return {
        "run_id": run_id,
        "research_id": f"research-{run_id}",
        "symbol": symbol,
        "target": target,
        "model": model,
        "start": start,
        "end": end,
        "oos_net": oos_net,
    }


def _write_backtest(root: Path, case: dict) -> None:
    run_dir = root / case["run_id"]
    run_dir.mkdir(parents=True)
    positive = case["oos_net"] > 0
    window_nets = [case["oos_net"] / 2, case["oos_net"] / 2, 0.0]
    windows = []
    for index, net in enumerate(window_nets, start=1):
        windows.append(
            {
                "window_id": index,
                "trades_validation": 20,
                "net_profit_validation": 8.0,
                "profit_factor_validation": 2.0,
                "win_rate_validation": 0.6,
                "expectancy_validation": 0.4,
                "sharpe_validation": 0.05,
                "max_drawdown_validation": 0.02,
                "trades_test": 20,
                "net_profit_test": net,
                "profit_factor_test": 2.0 if net > 0 else 0.8 if net < 0 else 0.0,
                "win_rate_test": 0.6 if net > 0 else 0.4 if net < 0 else 0.0,
                "expectancy_test": net / 20,
                "sharpe_test": 0.05 if net > 0 else -0.02 if net < 0 else 0.0,
                "max_drawdown_test": 0.02 if net >= 0 else 0.05,
            }
        )
    consolidated = {
        "total_windows": 3,
        "positive_test_windows": 2 if positive else 0,
        "negative_test_windows": 0 if positive else 2,
        "neutral_test_windows": 1,
        "aggregate_test_trades": 60,
        "aggregate_test_net_profit": case["oos_net"],
        "aggregate_test_profit_factor": 2.0 if positive else 0.8,
        "aggregate_test_win_rate": 0.6 if positive else 0.4,
        "aggregate_test_expectancy": case["oos_net"] / 60,
        "aggregate_test_sharpe": 0.05 if positive else -0.02,
        "aggregate_test_max_drawdown": 0.02 if positive else 0.05,
        "out_of_sample_positive": positive,
    }
    payloads = {
        "backtest_summary": {
            "number_of_trades": 100,
            "net_profit": 30.0 if positive else 2.0,
            "profit_factor": 2.5 if positive else 1.1,
            "win_rate": 0.65,
            "expectancy": 0.3 if positive else 0.02,
            "sharpe": 0.08 if positive else 0.01,
            "sortino": 0.1 if positive else 0.01,
            "max_drawdown": 0.02 if positive else 0.06,
        },
        "walk_forward_results": {"windows": windows, "consolidated": consolidated},
        "monthly_results": [{"month": "2026-01", "net_pnl": case["oos_net"]}],
        "run_metadata": {
            "run_id": case["run_id"],
            "engine_version": "v2",
            "symbol": case["symbol"],
            "interval": "5m",
            "target_name": case["target"],
            "model_name": case["model"],
            "period_start": case["start"],
            "period_end": case["end"],
            "timestamp": case["end"],
            "temporal_integrity_valid": True,
        },
    }
    for name, payload in payloads.items():
        (run_dir / f"{name}.json").write_text(json.dumps(payload))


def _write_research(root: Path, case: dict) -> None:
    run_dir = root / case["research_id"]
    run_dir.mkdir(parents=True)
    positive = case["oos_net"] > 0
    payloads = {
        "research_summary": {"robustness_score": 75 if positive else 40},
        "robustness_analysis": {"robustness_score": 75 if positive else 40, "classification": "Bom" if positive else "Regular"},
        "monte_carlo": {"probability_of_profit": 0.9 if positive else 0.4, "var_net_profit": 5.0 if positive else -5.0},
        "bootstrap": {
            "net_profit": {"ci_lower": 5.0 if positive else -5.0},
            "profit_factor": {"ci_lower": 1.2 if positive else 0.8},
            "expectancy": {"ci_lower": 0.1 if positive else -0.1},
            "sharpe": {"ci_lower": 0.01 if positive else -0.01},
        },
        "recommendation": {"ready_for_paper_trading": positive, "ready_for_live_trading": False},
        "run_metadata": {
            "research_run_id": case["research_id"],
            "source_backtest_run_id": case["run_id"],
            "source_timestamp": case["end"],
        },
    }
    for name, payload in payloads.items():
        (run_dir / f"{name}.json").write_text(json.dumps(payload))
