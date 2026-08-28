from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from ..backtests.engine import run_long_only_backtest
from ..config import get_settings
from ..features.builder import FEATURE_VERSION, build_features
from ..models.baseline import train_baseline
from ..signals.generator import generate_signal
from ..storage.database import create_sync_engine
from ..storage.repositories import CandleRepository
from ..targets.builder import build_direction_target

FEATURE_COLUMNS = [
    "return_1",
    "return_3",
    "return_12",
    "ema_9",
    "ema_21",
    "volatility_12",
    "volume_zscore_24",
    "range_pct",
    "rsi_14",
]

HORIZON_CANDLES = 12
THRESHOLD_PCT = 0.005
MODEL_VERSION = "logistic_v1"
TARGET_NAME = "direction_12_0_5pct"


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _persist_features(engine, frame: pd.DataFrame) -> int:
    rows: list[dict[str, Any]] = []
    usable = frame.dropna(subset=FEATURE_COLUMNS)
    for row in usable.itertuples(index=False):
        features = {column: _json_safe(getattr(row, column)) for column in FEATURE_COLUMNS}
        rows.append({
            "candle_id": int(row.id),
            "feature_version": FEATURE_VERSION,
            "features": json.dumps(features, ensure_ascii=False),
        })

    if not rows:
        return 0

    statement = text("""
        INSERT INTO crypto_features (candle_id, feature_version, features)
        VALUES (:candle_id, :feature_version, CAST(:features AS JSONB))
        ON CONFLICT (candle_id, feature_version)
        DO UPDATE SET features = EXCLUDED.features;
    """)
    with engine.begin() as connection:
        connection.execute(statement, rows)
    return len(rows)


def _persist_targets(engine, frame: pd.DataFrame) -> int:
    usable = frame.dropna(subset=["future_return"])
    rows = [
        {
            "candle_id": int(row.id),
            "target_name": TARGET_NAME,
            "horizon_candles": HORIZON_CANDLES,
            "threshold_pct": THRESHOLD_PCT,
            "target_value": _json_safe(row.future_return),
            "target_class": int(row.target_class),
        }
        for row in usable.itertuples(index=False)
    ]
    if not rows:
        return 0

    statement = text("""
        INSERT INTO crypto_targets (
            candle_id, target_name, horizon_candles,
            threshold_pct, target_value, target_class
        ) VALUES (
            :candle_id, :target_name, :horizon_candles,
            :threshold_pct, :target_value, :target_class
        )
        ON CONFLICT (candle_id, target_name, horizon_candles)
        DO UPDATE SET
            threshold_pct = EXCLUDED.threshold_pct,
            target_value = EXCLUDED.target_value,
            target_class = EXCLUDED.target_class;
    """)
    with engine.begin() as connection:
        connection.execute(statement, rows)
    return len(rows)


def _persist_signals(engine, symbol: str, interval: str, frame: pd.DataFrame) -> int:
    rows = []
    for row in frame.itertuples(index=False):
        reason = {
            "probability_up": _json_safe(row.probability_up),
            "thresholds": {"buy": 0.62, "sell": 0.38},
            "feature_version": FEATURE_VERSION,
        }
        rows.append({
            "symbol": symbol,
            "interval": interval,
            "signal_time": row.open_time,
            "model_version": MODEL_VERSION,
            "side": row.signal,
            "probability": _json_safe(row.signal_probability),
            "score": _json_safe(row.probability_up),
            "reason": json.dumps(reason, ensure_ascii=False),
        })

    if not rows:
        return 0

    # Mantém o script idempotente mesmo sem constraint única na tabela.
    with engine.begin() as connection:
        connection.execute(
            text("""
                DELETE FROM trading_signals
                WHERE symbol = :symbol
                  AND interval = :interval
                  AND model_version = :model_version;
            """),
            {"symbol": symbol, "interval": interval, "model_version": MODEL_VERSION},
        )
        connection.execute(
            text("""
                INSERT INTO trading_signals (
                    symbol, interval, signal_time, model_version,
                    side, probability, score, reason
                ) VALUES (
                    :symbol, :interval, :signal_time, :model_version,
                    :side, :probability, :score, CAST(:reason AS JSONB)
                );
            """),
            rows,
        )
    return len(rows)


def _persist_backtest(engine, symbol: str, interval: str, metrics: dict[str, Any]) -> int:
    parameters = {
        "symbol": symbol,
        "interval": interval,
        "feature_version": FEATURE_VERSION,
        "model_version": MODEL_VERSION,
        "horizon_candles": HORIZON_CANDLES,
        "threshold_pct": THRESHOLD_PCT,
        "feature_columns": FEATURE_COLUMNS,
    }
    statement = text("""
        INSERT INTO backtest_runs (
            name, strategy_version, started_at, finished_at,
            parameters, metrics, status
        ) VALUES (
            :name, :strategy_version, :started_at, :finished_at,
            CAST(:parameters AS JSONB), CAST(:metrics AS JSONB), 'COMPLETED'
        ) RETURNING id;
    """)
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        return int(connection.execute(statement, {
            "name": f"baseline_{symbol}_{interval}",
            "strategy_version": MODEL_VERSION,
            "started_at": now,
            "finished_at": now,
            "parameters": json.dumps(parameters, ensure_ascii=False),
            "metrics": json.dumps(metrics, ensure_ascii=False, default=_json_safe),
        }).scalar_one())


def process_symbol(engine, symbol: str, interval: str) -> dict[str, Any]:
    repository = CandleRepository(engine)
    candles = repository.load(symbol=symbol, interval=interval, limit=10000)
    if len(candles) < 200:
        raise ValueError(f"{symbol}: apenas {len(candles)} candles; mínimo recomendado: 200.")

    frame = build_features(candles)
    frame = build_direction_target(
        frame,
        horizon_candles=HORIZON_CANDLES,
        threshold_pct=THRESHOLD_PCT,
    )

    features_saved = _persist_features(engine, frame)
    targets_saved = _persist_targets(engine, frame)

    model_frame = frame.dropna(subset=FEATURE_COLUMNS + ["target_class"]).copy()
    split_index = int(len(model_frame) * 0.70)
    train = model_frame.iloc[:split_index].copy()
    validation = model_frame.iloc[split_index:].copy()

    train_classes = sorted(train.loc[train["target_class"].isin([0, 1]), "target_class"].unique().tolist())
    valid_classes = sorted(validation.loc[validation["target_class"].isin([0, 1]), "target_class"].unique().tolist())
    if len(train_classes) < 2 or len(valid_classes) < 2:
        raise ValueError(
            f"{symbol}: classes insuficientes para treino/validação. "
            f"Treino={train_classes}, validação={valid_classes}."
        )

    baseline = train_baseline(
        train=train,
        validation=validation,
        feature_columns=FEATURE_COLUMNS,
    )

    validation_ready = validation.dropna(subset=FEATURE_COLUMNS).copy()
    validation_ready["probability_up"] = baseline.model.predict_proba(
        validation_ready[FEATURE_COLUMNS]
    )[:, 1]

    generated = validation_ready["probability_up"].apply(generate_signal)
    validation_ready["signal"] = generated.map(lambda item: item.side)
    validation_ready["signal_probability"] = generated.map(lambda item: item.probability)
    validation_ready["signal_reason"] = generated.map(lambda item: item.reason)

    signals_saved = _persist_signals(engine, symbol, interval, validation_ready)

    settings = get_settings()
    backtest = run_long_only_backtest(
        validation_ready,
        initial_cash=10_000.0,
        fee_bps=settings.trading_fee_bps,
        slippage_bps=settings.trading_slippage_bps,
    )

    metrics = {
        **backtest.metrics,
        "roc_auc": baseline.metrics["roc_auc"],
        "candles": int(len(candles)),
        "train_rows": int(len(train)),
        "validation_rows": int(len(validation_ready)),
        "buy_signals": int((validation_ready["signal"] == "BUY").sum()),
        "sell_signals": int((validation_ready["signal"] == "SELL").sum()),
        "hold_signals": int((validation_ready["signal"] == "HOLD").sum()),
    }
    backtest_id = _persist_backtest(engine, symbol, interval, metrics)

    latest = validation_ready.iloc[-1]
    return {
        "symbol": symbol,
        "interval": interval,
        "candles": len(candles),
        "features_saved": features_saved,
        "targets_saved": targets_saved,
        "signals_saved": signals_saved,
        "backtest_id": backtest_id,
        "latest_signal": latest["signal"],
        "latest_probability_up": float(latest["probability_up"]),
        "metrics": metrics,
    }


def main() -> int:
    settings = get_settings()
    if settings.trading_mode != "PAPER_ONLY":
        print("Execução bloqueada: este pipeline exige TRADING_MODE=PAPER_ONLY.", file=sys.stderr)
        return 1

    engine = create_sync_engine(settings.database_url)
    print("=" * 72)
    print("VINANCE TRADING PIPELINE — FEATURES → TARGETS → ML → BACKTEST")
    print("=" * 72)
    print(f"Modo: {settings.trading_mode}")
    print(f"Ativos: {settings.trading_symbols}")
    print(f"Intervalo: {settings.trading_interval}")

    results = []
    failures = []
    try:
        for symbol in settings.trading_symbols:
            print(f"\nProcessando {symbol}...")
            try:
                result = process_symbol(engine, symbol, settings.trading_interval)
                results.append(result)
                metrics = result["metrics"]
                print(
                    f"{symbol}: features={result['features_saved']}, "
                    f"targets={result['targets_saved']}, sinais={result['signals_saved']}"
                )
                print(
                    f"{symbol}: AUC={metrics['roc_auc']:.4f}, "
                    f"retorno={metrics['return_pct']:.2f}%, "
                    f"drawdown={metrics['max_drawdown_pct']:.2f}%"
                )
                print(
                    f"{symbol}: sinal atual={result['latest_signal']} "
                    f"(P(alta)={result['latest_probability_up']:.4f})"
                )
            except Exception as error:
                failures.append({"symbol": symbol, "error": str(error)})
                print(f"{symbol}: ERRO — {error}", file=sys.stderr)

        output_dir = Path("/app/backend/trading/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"pipeline_{datetime.now():%Y%m%d_%H%M%S}.json"
        report_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "results": results,
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
                default=_json_safe,
            ),
            encoding="utf-8",
        )

        print("\n" + "=" * 72)
        print(f"Concluídos: {len(results)} | Falhas: {len(failures)}")
        print(f"Relatório: {report_path}")
        return 0 if results else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
