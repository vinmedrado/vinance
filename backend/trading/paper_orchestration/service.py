from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.trading.config import get_settings
from backend.trading.model_registry import RegistryEntry, TradingModelRegistry, get_registry
from backend.trading.paper_trading_v2.executor import parse_target_name
from backend.trading.prediction_engine.config import PredictionEngineConfig
from backend.trading.prediction_engine.decision import AVOID, BUY_CANDIDATE, HOLD
from backend.trading.prediction_engine.models import ManifestEntry, PredictionResult
from backend.trading.prediction_engine.pipeline import PredictionEngine
from backend.trading.prediction_engine.repository import PredictionRepository
from backend.trading.storage.migrate import LATEST_TRADING_SCHEMA_VERSION


@dataclass(frozen=True)
class SignalPlan:
    prediction_id: str
    candle_id: int
    symbol: str
    interval: str
    signal_time: datetime
    freshness_expires_at: datetime
    model_version: str
    side: str
    probability: Decimal
    score: Decimal
    reference_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    feature_version: str
    target_version: str
    target_name: str
    guardrail_status: str
    reason: dict[str, Any]


def _interval_duration(interval: str) -> timedelta:
    match = re.fullmatch(r"([1-9]\d*)([mhd])", interval.strip().lower())
    if not match:
        raise ValueError(f"Unsupported Trading interval: {interval}")
    amount, unit = match.groups()
    seconds = int(amount) * {"m": 60, "h": 3600, "d": 86400}[unit]
    return timedelta(seconds=seconds)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _positive_decimal(value: Any, *, label: str) -> Decimal:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{label} must be a finite positive value")
    return Decimal(str(value))


def _assert_registry_match(entry: RegistryEntry, result: PredictionResult) -> None:
    expected = {
        "symbol": entry.symbol,
        "interval": entry.interval,
        "target_name": entry.target_name,
        "model_name": entry.model_name,
        "model_version": entry.version,
        "feature_version": entry.feature_version,
    }
    actual = {
        "symbol": result.symbol,
        "interval": result.interval,
        "target_name": result.target_name,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "feature_version": result.feature_version,
    }
    mismatches = [key for key in expected if expected[key] != actual[key]]
    if mismatches:
        raise RuntimeError(
            "Prediction does not match the promoted registry artifact: "
            + ", ".join(sorted(mismatches))
        )
    if entry.promotion_status != "PAPER_ACTIVE" or entry.validation_status != "PAPER_READY":
        raise RuntimeError("Only a Validation V2 PAPER_READY/PAPER_ACTIVE model may emit Paper signals")


def build_signal_plan(
    *,
    entry: RegistryEntry,
    result: PredictionResult,
    reference_price: Any,
    now: datetime | None = None,
) -> SignalPlan:
    """Build one explainable signal without placing or simulating an order."""

    _assert_registry_match(entry, result)
    current_time = _aware_utc(now or datetime.now(timezone.utc))
    signal_time = _aware_utc(result.open_time)
    # A prediction produced from a completed bar is useful for the immediately
    # following bar only.  This is a temporal-integrity rule, not a return or
    # risk threshold, and prevents old research signals becoming opportunities.
    expires_at = signal_time + (2 * _interval_duration(result.interval))
    is_fresh = expires_at >= current_time
    price = _positive_decimal(reference_price, label="reference_price")
    target_rules = parse_target_name(result.target_name)
    stop_price = price * Decimal(str(1 - target_rules.stop_loss_pct))
    target_price = price * Decimal(str(1 + target_rules.take_profit_pct))

    if result.decision == BUY_CANDIDATE and is_fresh:
        guardrail = "APPROVED"
    elif result.decision == HOLD:
        guardrail = "WARNING"
    elif result.decision in {BUY_CANDIDATE, AVOID}:
        guardrail = "BLOCKED"
    else:
        raise ValueError(f"Unsupported Prediction Engine decision: {result.decision}")

    reason = {
        "paper_only": True,
        "model_id": entry.model_id,
        "model_name": result.model_name,
        "prediction_engine_version": result.prediction_engine_version,
        "confidence": result.confidence,
        "confidence_level": result.confidence_level,
        "probability_take_profit": result.probability_take_profit,
        "probability_stop_loss": result.probability_stop_loss,
        "probability_neutral": result.probability_neutral,
        "risk_score": result.risk_score,
        "expected_return": result.expected_return,
        "expected_drawdown": result.expected_drawdown,
        "decision": result.decision,
        "decision_reason": result.reason.get("decision_reason"),
        "fresh": is_fresh,
        "freshness_policy": "source_bar_plus_one_interval",
        "continuous_scheduler_enabled": False,
        "reasons": [
            (
                "Sinal atual de modelo validado para simulação Paper."
                if guardrail == "APPROVED"
                else "Sinal não elegível como oportunidade Paper atual."
            )
        ],
    }
    return SignalPlan(
        prediction_id=result.prediction_id,
        candle_id=result.candle_id,
        symbol=result.symbol,
        interval=result.interval,
        signal_time=signal_time,
        freshness_expires_at=expires_at,
        model_version=result.model_version,
        side=result.decision,
        probability=Decimal(str(result.confidence)),
        score=Decimal(str(result.expected_return)),
        reference_price=price,
        stop_price=stop_price,
        target_price=target_price,
        feature_version=result.feature_version,
        target_version=target_rules.target_version,
        target_name=result.target_name,
        guardrail_status=guardrail,
        reason=reason,
    )


class ManualPaperOrchestrator:
    """Explicit run-once bridge from promoted model to persisted Paper signal.

    It never opens orders or positions and is intentionally not registered in
    Celery Beat.  A future scheduler can invoke this same service only after a
    separate product authorization.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        registry: TradingModelRegistry | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.engine = engine
        self.registry = registry or get_registry()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def status(self) -> dict[str, Any]:
        schema = self._schema_version()
        registry_health = self.registry.health()
        return {
            "paper_only": get_settings().trading_mode == "PAPER_ONLY",
            "schema_version": schema,
            "schema_compatible": schema == LATEST_TRADING_SCHEMA_VERSION,
            "registry": registry_health,
            "scheduler_enabled": False,
        }

    def run_once(self) -> dict[str, Any]:
        if get_settings().trading_mode != "PAPER_ONLY":
            raise RuntimeError("Manual Paper orchestration requires PAPER_ONLY mode")
        if self._schema_version() != LATEST_TRADING_SCHEMA_VERSION:
            raise RuntimeError("Trading external schema is incompatible")
        active = self.registry.active()
        if not active:
            return {
                "status": "NO_PAPER_ACTIVE_MODELS",
                "evaluated": 0,
                "inserted": 0,
                "scheduler_enabled": False,
            }

        inserted = 0
        results: list[dict[str, Any]] = []
        for entry in active:
            plan = self._evaluate(entry)
            was_inserted, signal_id = self._persist(plan)
            inserted += int(was_inserted)
            results.append(
                {
                    "prediction_id": plan.prediction_id,
                    "signal_id": signal_id,
                    "symbol": plan.symbol,
                    "guardrail_status": plan.guardrail_status,
                    "inserted": was_inserted,
                }
            )
        return {
            "status": "COMPLETED",
            "evaluated": len(results),
            "inserted": inserted,
            "scheduler_enabled": False,
            "results": results,
        }

    def _schema_version(self) -> str | None:
        with self.engine.connect() as connection:
            try:
                return connection.execute(
                    text("SELECT version FROM trading_schema_version WHERE id = 1")
                ).scalar_one_or_none()
            except Exception:
                return None

    def _evaluate(self, entry: RegistryEntry) -> SignalPlan:
        config = PredictionEngineConfig(
            feature_version=entry.feature_version,
            artifacts_root=self.registry.artifacts_root,
        )
        repository = PredictionRepository(self.engine, config)
        repository.ensure_schema()
        manifest_entry = ManifestEntry(
            symbol=entry.symbol,
            interval=entry.interval,
            target_name=entry.target_name,
            model_name=entry.model_name,
            feature_version=entry.feature_version,
            ml_engine_version=entry.version,
            is_best=False,
            artifact_dir=entry.artifact_dir,
            generated_at=entry.created_at,
            metadata={"model_id": entry.model_id, "promotion_status": entry.promotion_status},
        )
        result = PredictionEngine(repository, config=config).predict_entry(manifest_entry)
        with self.engine.connect() as connection:
            reference_price = connection.execute(
                text(
                    "SELECT close FROM crypto_candles "
                    "WHERE id = :candle_id AND symbol = :symbol AND interval = :interval"
                ),
                {
                    "candle_id": result.candle_id,
                    "symbol": result.symbol,
                    "interval": result.interval,
                },
            ).scalar_one()
        return build_signal_plan(
            entry=entry,
            result=result,
            reference_price=reference_price,
            now=self.clock(),
        )

    def _persist(self, plan: SignalPlan) -> tuple[bool, int]:
        values = asdict(plan)
        values["reason"] = json.dumps(
            values["reason"], sort_keys=True, separators=(",", ":"), default=str
        )
        with self.engine.begin() as connection:
            inserted_id = connection.execute(
                text(
                    """
                    INSERT INTO trading_signals (
                        symbol, interval, signal_time, model_version, side,
                        probability, score, reason, prediction_id, candle_id,
                        feature_version, target_version, target_name,
                        reference_price, stop_price, target_price,
                        freshness_expires_at, guardrail_status, paper_only
                    ) VALUES (
                        :symbol, :interval, :signal_time, :model_version, :side,
                        :probability, :score, CAST(:reason AS JSONB), :prediction_id,
                        :candle_id, :feature_version, :target_version, :target_name,
                        :reference_price, :stop_price, :target_price,
                        :freshness_expires_at, :guardrail_status, TRUE
                    )
                    ON CONFLICT (prediction_id) WHERE prediction_id IS NOT NULL
                    DO NOTHING
                    RETURNING id
                    """
                ),
                values,
            ).scalar_one_or_none()
            if inserted_id is not None:
                return True, int(inserted_id)
            existing_id = connection.execute(
                text(
                    "SELECT id FROM trading_signals "
                    "WHERE prediction_id = :prediction_id"
                ),
                {"prediction_id": plan.prediction_id},
            ).scalar_one()
            return False, int(existing_id)
