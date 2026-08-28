from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from ..backtests.advanced import run_advanced_long_backtest
from ..config import get_settings
from ..features.builder import FEATURE_VERSION, build_features
from ..models.baseline import train_baseline
from ..storage.database import create_sync_engine
from ..storage.repositories import CandleRepository
from ..targets.builder import build_direction_target

FEATURE_COLUMNS = [
    "return_1", "return_3", "return_12", "ema_9", "ema_21",
    "volatility_12", "volume_zscore_24", "range_pct", "rsi_14",
]
HORIZON_CANDLES = 12
THRESHOLD_PCT = 0.005
MODEL_VERSION = "logistic_research_v2"
TARGET_NAME = "direction_12_0_5pct"
MIN_CANDLES = 5000


def json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,)): return None if np.isnan(value) or np.isinf(value) else float(value)
    if isinstance(value, (pd.Timestamp, datetime)): return value.isoformat()
    if value is None or pd.isna(value): return None
    return value


def persist_backtest(engine, symbol: str, interval: str, metrics: dict[str, Any], parameters: dict[str, Any]) -> int:
    now = datetime.now(timezone.utc)
    statement = text("""
        INSERT INTO backtest_runs (
            name, strategy_version, started_at, finished_at,
            parameters, metrics, status
        ) VALUES (
            :name, :strategy_version, :started_at, :finished_at,
            CAST(:parameters AS JSONB), CAST(:metrics AS JSONB), 'COMPLETED'
        ) RETURNING id;
    """)
    with engine.begin() as connection:
        return int(connection.execute(statement, {
            "name": f"research_{symbol}_{interval}",
            "strategy_version": MODEL_VERSION,
            "started_at": now,
            "finished_at": now,
            "parameters": json.dumps(parameters, ensure_ascii=False),
            "metrics": json.dumps(metrics, ensure_ascii=False, default=json_safe),
        }).scalar_one())


def evaluate_window(train: pd.DataFrame, validation: pd.DataFrame) -> tuple[Any, pd.DataFrame, float]:
    baseline = train_baseline(train, validation, FEATURE_COLUMNS)
    ready = validation.dropna(subset=FEATURE_COLUMNS).copy()
    ready["probability_up"] = baseline.model.predict_proba(ready[FEATURE_COLUMNS])[:, 1]
    return baseline, ready, float(baseline.metrics["roc_auc"])


def process_symbol(engine, symbol: str, interval: str) -> dict[str, Any]:
    candles = CandleRepository(engine).load(symbol=symbol, interval=interval, limit=100000)
    if len(candles) < MIN_CANDLES:
        raise ValueError(f"{symbol}: {len(candles)} candles; mínimo para pesquisa: {MIN_CANDLES}.")

    frame = build_direction_target(
        build_features(candles),
        horizon_candles=HORIZON_CANDLES,
        threshold_pct=THRESHOLD_PCT,
    ).dropna(subset=FEATURE_COLUMNS + ["target_class"]).reset_index(drop=True)

    # Walk-forward simples: três janelas cronológicas crescentes.
    cut1 = int(len(frame) * 0.55)
    cut2 = int(len(frame) * 0.70)
    cut3 = int(len(frame) * 0.85)
    windows = [(0, cut1, cut1, cut2), (0, cut2, cut2, cut3), (0, cut3, cut3, len(frame))]

    validation_parts = []
    aucs = []
    for train_start, train_end, valid_start, valid_end in windows:
        train = frame.iloc[train_start:train_end].copy()
        validation = frame.iloc[valid_start:valid_end].copy()
        baseline, ready, auc = evaluate_window(train, validation)
        validation_parts.append(ready)
        aucs.append(auc)

    validation_all = pd.concat(validation_parts, ignore_index=True).sort_values("open_time")
    settings = get_settings()
    backtest = run_advanced_long_backtest(
        validation_all,
        initial_cash=10_000.0,
        fee_bps=settings.trading_fee_bps,
        slippage_bps=settings.trading_slippage_bps,
        buy_threshold=0.65,
        exit_threshold=0.48,
        stop_loss_pct=0.015,
        take_profit_pct=0.025,
        max_bars_in_trade=36,
        cooldown_bars=6,
    )

    metrics = {
        **backtest.metrics,
        "roc_auc_mean": float(np.mean(aucs)),
        "roc_auc_windows": aucs,
        "candles": int(len(candles)),
        "research_rows": int(len(frame)),
        "validation_rows": int(len(validation_all)),
    }
    parameters = {
        "symbol": symbol,
        "interval": interval,
        "feature_version": FEATURE_VERSION,
        "model_version": MODEL_VERSION,
        "features": FEATURE_COLUMNS,
        "walk_forward_windows": 3,
        "buy_threshold": 0.65,
        "exit_threshold": 0.48,
        "stop_loss_pct": 0.015,
        "take_profit_pct": 0.025,
        "max_bars_in_trade": 36,
        "cooldown_bars": 6,
    }
    backtest_id = persist_backtest(engine, symbol, interval, metrics, parameters)

    output_dir = Path("/app/backend/trading/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not backtest.trades.empty:
        backtest.trades.to_csv(output_dir / f"trades_{symbol}_{interval}.csv", index=False)

    latest = validation_all.iloc[-1]
    return {
        "symbol": symbol,
        "interval": interval,
        "backtest_id": backtest_id,
        "latest_probability_up": float(latest["probability_up"]),
        "metrics": metrics,
    }


def main() -> int:
    settings = get_settings()
    if settings.trading_mode != "PAPER_ONLY":
        print("Execução bloqueada: use TRADING_MODE=PAPER_ONLY.", file=sys.stderr)
        return 1

    engine = create_sync_engine(settings.database_url)
    results, failures = [], []
    print("=" * 72)
    print("VINANCE RESEARCH PIPELINE — WALK-FORWARD + RISCO + BACKTEST")
    print("=" * 72)
    try:
        for symbol in settings.trading_symbols:
            print(f"\nProcessando {symbol}...")
            try:
                result = process_symbol(engine, symbol, settings.trading_interval)
                results.append(result)
                m = result["metrics"]
                print(f"{symbol}: AUC médio={m['roc_auc_mean']:.4f}")
                print(f"{symbol}: retorno={m['return_pct']:.2f}% | buy&hold={m['buy_hold_return_pct']:.2f}%")
                print(f"{symbol}: drawdown={m['max_drawdown_pct']:.2f}% | trades={m['trades']} | win rate={m['win_rate_pct']:.2f}%")
                print(f"{symbol}: profit factor={m['profit_factor']:.2f} | Sharpe={m['sharpe']:.2f}")
            except Exception as error:
                failures.append({"symbol": symbol, "error": str(error)})
                print(f"{symbol}: ERRO — {error}", file=sys.stderr)

        output_dir = Path("/app/backend/trading/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"research_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
            "failures": failures,
        }, ensure_ascii=False, indent=2, default=json_safe), encoding="utf-8")
        print("\n" + "=" * 72)
        print(f"Concluídos: {len(results)} | Falhas: {len(failures)}")
        print(f"Relatório: {path}")
        return 0 if results else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
