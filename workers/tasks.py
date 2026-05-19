
from __future__ import annotations

import subprocess
import sys

from workers.celery_app import app


@app.task
def sync_all_prices(tenant_id: str = "default", asset_class: str = "equity"):
    result = subprocess.run(
        [sys.executable, "scripts/sync_historical_prices.py", f"--asset-class={asset_class}"],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return {
        "tenant_id": tenant_id,
        "asset_class": asset_class,
        "returncode": result.returncode,
        "stdout": result.stdout[-500:],
        "stderr": result.stderr[-200:],
    }


@app.task
def run_ml_predictions(tenant_id: str = "default", model_id: int | None = None):
    if not model_id:
        return {"status": "skipped", "reason": "model_id ausente"}
    from services.ml_prediction_service import predict
    return predict(model_id=model_id, asset_class="all", limit=100)


@app.task
def check_drift(tenant_id: str = "default"):
    try:
        from services.ml_model_registry import get_best_model
        from services.ml_drift_service import check_drift_for_model
        model = get_best_model()
        if not model:
            return {"status": "no_model"}
        features = ["rsi_14", "macd_signal", "momentum_21", "volume_ratio"]
        result = check_drift_for_model(model_id=model["id"], features=features)
        return {"status": "ok", "drift_score": result.get("drift_score"), "action": result.get("action_taken")}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.task
def send_alert_email(user_id: str, alert_type: str, payload: dict):
    from services.alert_engine import send_alert_email as send
    return send(user_id, alert_type, payload)


@app.task
def run_backtest_async(tenant_id: str, strategy_params: dict):
    try:
        cmd = [sys.executable, "scripts/run_strategy_backtest.py"]
        for key, value in (strategy_params or {}).items():
            if isinstance(value, (str, int, float, bool)):
                cmd.append(f"--{key.replace('_','-')}={value}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "tenant_id": tenant_id,
            "returncode": result.returncode,
            "stdout": result.stdout[-500:],
            "stderr": result.stderr[-300:],
            "params": strategy_params,
        }
    except FileNotFoundError:
        return {"status": "skipped", "reason": "scripts/run_strategy_backtest.py não encontrado", "params": strategy_params}
    except Exception as e:
        return {"status": "error", "error": str(e), "params": strategy_params}


@app.task
def run_quant_backtest(job_id: str, payload: dict):
    from backend.app.quant_intelligence.schemas import BacktestRequest
    from backend.app.quant_intelligence.service import run_backtest, update_job
    try:
        update_job(job_id, status="running")
        result = run_backtest(BacktestRequest(**(payload or {})))
        update_job(job_id, status="completed", result=result)
        return {"status": "completed", "job_id": job_id, "result": result}
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))
        return {"status": "failed", "job_id": job_id, "error": str(exc)}


@app.task
def run_quant_training(job_id: str, payload: dict):
    from backend.app.quant_intelligence.schemas import TrainModelRequest
    from backend.app.quant_intelligence.service import train_model, update_job
    try:
        update_job(job_id, status="running")
        result = train_model(TrainModelRequest(**(payload or {})))
        update_job(job_id, status="completed", result=result)
        return {"status": "completed", "job_id": job_id, "result": result}
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))
        return {"status": "failed", "job_id": job_id, "error": str(exc)}


@app.task
def sync_quant_market_data(job_id: str | None = None):
    from backend.app.quant_intelligence.service import sync_market_snapshots, update_job
    try:
        result = sync_market_snapshots(source="celery_schedule")
        if job_id:
            update_job(job_id, status="completed", result=result)
        return result
    except Exception as exc:
        if job_id:
            update_job(job_id, status="failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}
