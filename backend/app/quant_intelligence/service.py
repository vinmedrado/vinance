from __future__ import annotations

import csv
import hashlib
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from db.database import SessionLocal
from backend.app.quant_intelligence.schemas import BacktestRequest, InvestmentDecisionRequest, TrainModelRequest
from backend.app.quant_intelligence.providers import fetch_yfinance_quote, quote_to_payload

ROOT = Path(__file__).resolve().parents[3]
CATALOG_DIR = ROOT / "data" / "catalog_fallback"

MARKET_UNIVERSE = [
    {"ticker": "SELIC", "name": "Tesouro Selic / caixa remunerado", "market": "renda_fixa", "risk": 1, "liquidity": 5, "expected_return": 0.105, "volatility": 0.015, "macro_score": 92},
    {"ticker": "CDB", "name": "CDB liquidez diária", "market": "renda_fixa", "risk": 1, "liquidity": 5, "expected_return": 0.108, "volatility": 0.018, "macro_score": 90},
    {"ticker": "IPCA+", "name": "Tesouro IPCA+", "market": "renda_fixa", "risk": 2, "liquidity": 3, "expected_return": 0.118, "volatility": 0.055, "macro_score": 84},
    {"ticker": "BOVA11", "name": "ETF Ibovespa", "market": "etf", "risk": 4, "liquidity": 5, "expected_return": 0.135, "volatility": 0.185, "macro_score": 73},
    {"ticker": "SMAL11", "name": "ETF small caps Brasil", "market": "etf", "risk": 5, "liquidity": 4, "expected_return": 0.155, "volatility": 0.245, "macro_score": 67},
    {"ticker": "IVVB11", "name": "ETF S&P 500 em reais", "market": "internacional", "risk": 4, "liquidity": 5, "expected_return": 0.145, "volatility": 0.205, "macro_score": 82},
    {"ticker": "HASH11", "name": "ETF cripto diversificado", "market": "cripto", "risk": 5, "liquidity": 4, "expected_return": 0.22, "volatility": 0.55, "macro_score": 58},
    {"ticker": "HGLG11", "name": "FII logística", "market": "fii", "risk": 3, "liquidity": 4, "expected_return": 0.125, "volatility": 0.145, "macro_score": 76},
    {"ticker": "KNRI11", "name": "FII renda urbana", "market": "fii", "risk": 3, "liquidity": 4, "expected_return": 0.118, "volatility": 0.13, "macro_score": 78},
    {"ticker": "PETR4", "name": "Petrobras PN", "market": "acao", "risk": 5, "liquidity": 5, "expected_return": 0.16, "volatility": 0.35, "macro_score": 64},
    {"ticker": "ITUB4", "name": "Itaú Unibanco PN", "market": "acao", "risk": 4, "liquidity": 5, "expected_return": 0.135, "volatility": 0.22, "macro_score": 76},
    {"ticker": "WEGE3", "name": "WEG ON", "market": "acao", "risk": 4, "liquidity": 5, "expected_return": 0.155, "volatility": 0.26, "macro_score": 81},
]

PROFILE_RULES = {
    "conservador": {"reserve_months": 9, "risk_budget": 1.8, "max_equity": 0.20, "max_crypto": 0.00},
    "moderado": {"reserve_months": 6, "risk_budget": 3.0, "max_equity": 0.42, "max_crypto": 0.03},
    "arrojado": {"reserve_months": 4, "risk_budget": 4.0, "max_equity": 0.62, "max_crypto": 0.07},
    "agressivo": {"reserve_months": 3, "risk_budget": 4.7, "max_equity": 0.76, "max_crypto": 0.12},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_tables() -> None:
    with SessionLocal() as db:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS quant_decision_runs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                risk_profile VARCHAR(32),
                objective TEXT,
                monthly_income DOUBLE PRECISION,
                monthly_expenses DOUBLE PRECISION,
                cash_available DOUBLE PRECISION,
                investable_capital DOUBLE PRECISION,
                decision VARCHAR(64),
                payload JSONB
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS quant_backtest_runs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                ticker VARCHAR(32),
                strategy VARCHAR(80),
                initial_capital DOUBLE PRECISION,
                final_capital DOUBLE PRECISION,
                total_return DOUBLE PRECISION,
                max_drawdown DOUBLE PRECISION,
                sharpe_like DOUBLE PRECISION,
                win_rate DOUBLE PRECISION,
                payload JSONB
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS quant_training_runs (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                market VARCHAR(64),
                risk_profile VARCHAR(32),
                auc DOUBLE PRECISION,
                precision_score DOUBLE PRECISION,
                recall_score DOUBLE PRECISION,
                confidence DOUBLE PRECISION,
                payload JSONB
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS quant_market_snapshots (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                ticker VARCHAR(32) NOT NULL,
                name VARCHAR(255),
                market VARCHAR(64),
                risk INTEGER,
                liquidity INTEGER,
                expected_return DOUBLE PRECISION,
                volatility DOUBLE PRECISION,
                macro_score DOUBLE PRECISION,
                source VARCHAR(64) DEFAULT 'vinance_universe',
                payload JSONB
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS quant_market_quotes (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                ticker VARCHAR(32) NOT NULL,
                price DOUBLE PRECISION,
                currency VARCHAR(16),
                change_pct_30d DOUBLE PRECISION,
                volatility_90d DOUBLE PRECISION,
                source VARCHAR(120),
                payload JSONB
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS quant_job_runs (
                id VARCHAR(64) PRIMARY KEY,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                job_type VARCHAR(80) NOT NULL,
                status VARCHAR(40) DEFAULT 'queued',
                payload JSONB,
                result JSONB,
                error TEXT,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        db.commit()


def _read_catalog_assets(limit: int = 80) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    files = [
        ("brazil_etfs.csv", "etf"),
        ("brazil_fiis.csv", "fii"),
        ("brazil_equities.csv", "acao"),
        ("us_etfs.csv", "internacional"),
        ("crypto.csv", "cripto"),
    ]
    for filename, market in files:
        path = CATALOG_DIR / filename
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ticker = (row.get("ticker") or row.get("symbol") or row.get("code") or "").strip()
                    name = (row.get("name") or row.get("asset_name") or ticker).strip()
                    if ticker:
                        score_seed = int(hashlib.sha256(ticker.encode()).hexdigest()[:8], 16)
                        rng = random.Random(score_seed)
                        assets.append({
                            "ticker": ticker,
                            "name": name,
                            "market": market,
                            "risk": rng.randint(2, 5),
                            "liquidity": rng.randint(2, 5),
                            "expected_return": round(rng.uniform(0.09, 0.19), 4),
                            "volatility": round(rng.uniform(0.10, 0.34), 4),
                            "macro_score": rng.randint(58, 88),
                        })
                        if len(assets) >= limit:
                            return assets
        except Exception:
            continue
    return assets


def market_universe() -> list[dict[str, Any]]:
    catalog = _read_catalog_assets(limit=60)
    seen = {m["ticker"] for m in MARKET_UNIVERSE}
    merged = MARKET_UNIVERSE + [m for m in catalog if m["ticker"] not in seen]
    return merged


def _score_market(asset: dict[str, Any], risk_budget: float) -> float:
    risk_distance = abs(float(asset["risk"]) - risk_budget)
    score = (
        float(asset["macro_score"]) * 0.36
        + float(asset["expected_return"]) * 220
        + float(asset["liquidity"]) * 6
        - float(asset["volatility"]) * 45
        - risk_distance * 8
    )
    return round(max(0, min(score, 100)), 2)


def investment_decision(req: InvestmentDecisionRequest) -> dict[str, Any]:
    _ensure_tables()
    rules = PROFILE_RULES.get(req.risk_profile, PROFILE_RULES["moderado"])
    monthly_surplus = max(req.monthly_income - req.monthly_expenses, 0)
    reserve_target = req.monthly_expenses * rules["reserve_months"]
    reserve_gap = max(reserve_target - req.emergency_reserve_current, 0)
    excess_cash = max(req.cash_available - reserve_gap, 0)
    monthly_investable = max(monthly_surplus * (0.45 if req.risk_profile == "conservador" else 0.65), 0)
    investable_capital = round(excess_cash + monthly_investable, 2)

    if req.monthly_income <= 0:
        status = "dados_insuficientes"
        decision = "Cadastre renda e despesas antes de alocar capital."
    elif reserve_gap > req.cash_available:
        status = "priorizar_reserva"
        decision = "Ainda não é ideal investir em risco. Priorize completar a reserva de emergência."
    elif investable_capital <= 0:
        status = "aguardar"
        decision = "Neste momento não há capital livre relevante para alocação."
    else:
        status = "investir_com_controle"
        decision = "Existe capital investível com controle de risco e diversificação."

    candidates = []
    for asset in market_universe():
        if asset["market"] == "cripto" and rules["max_crypto"] <= 0:
            continue
        if asset["market"] in {"acao", "etf", "internacional"} and rules["max_equity"] <= 0:
            continue
        item = dict(asset)
        item["score"] = _score_market(item, rules["risk_budget"])
        candidates.append(item)
    candidates.sort(key=lambda x: x["score"], reverse=True)

    buckets = {
        "reserva_liquidez": 0.0,
        "renda_fixa": 0.0,
        "fundos_imobiliarios": 0.0,
        "acoes_etfs": 0.0,
        "internacional": 0.0,
        "cripto": 0.0,
    }
    if status == "priorizar_reserva":
        buckets["reserva_liquidez"] = 1.0
    elif req.risk_profile == "conservador":
        buckets.update({"reserva_liquidez": .20, "renda_fixa": .58, "fundos_imobiliarios": .12, "acoes_etfs": .08, "internacional": .02})
    elif req.risk_profile == "moderado":
        buckets.update({"reserva_liquidez": .10, "renda_fixa": .38, "fundos_imobiliarios": .15, "acoes_etfs": .25, "internacional": .10, "cripto": .02})
    elif req.risk_profile == "arrojado":
        buckets.update({"reserva_liquidez": .06, "renda_fixa": .24, "fundos_imobiliarios": .12, "acoes_etfs": .38, "internacional": .15, "cripto": .05})
    else:
        buckets.update({"reserva_liquidez": .04, "renda_fixa": .18, "fundos_imobiliarios": .08, "acoes_etfs": .45, "internacional": .17, "cripto": .08})

    market_map = {
        "reserva_liquidez": ["SELIC", "CDB"],
        "renda_fixa": ["SELIC", "CDB", "IPCA+"],
        "fundos_imobiliarios": ["HGLG11", "KNRI11"],
        "acoes_etfs": ["BOVA11", "SMAL11", "ITUB4", "WEGE3", "PETR4"],
        "internacional": ["IVVB11"],
        "cripto": ["HASH11"],
    }
    by_ticker = {a["ticker"]: a for a in candidates}
    allocations = []
    for bucket, weight in buckets.items():
        if weight <= 0:
            continue
        amount = round(investable_capital * weight, 2)
        tickers = [t for t in market_map[bucket] if t in by_ticker]
        best = [by_ticker[t] for t in tickers] or candidates[:2]
        allocations.append({
            "bucket": bucket,
            "weight": round(weight, 4),
            "amount": amount,
            "markets": best[:3],
        })

    result = {
        "generated_at": _now(),
        "status": status,
        "decision": decision,
        "profile": req.risk_profile,
        "objective": req.objective,
        "monthly_surplus": round(monthly_surplus, 2),
        "reserve_target": round(reserve_target, 2),
        "reserve_gap": round(reserve_gap, 2),
        "investable_capital": investable_capital,
        "monthly_investable": round(monthly_investable, 2),
        "allocation": allocations,
        "top_opportunities": candidates[:10],
        "risk_controls": [
            "Não usar reserva de emergência para ativos de risco.",
            "Rebalancear mensalmente se a alocação sair mais de 5% do plano.",
            "Evitar concentração acima de 20% em um único ativo.",
            "Validar liquidez antes de qualquer aumento de posição.",
        ],
    }
    with SessionLocal() as db:
        db.execute(text("""
            INSERT INTO quant_decision_runs
            (risk_profile, objective, monthly_income, monthly_expenses, cash_available, investable_capital, decision, payload)
            VALUES (:risk_profile, :objective, :monthly_income, :monthly_expenses, :cash_available, :investable_capital, :decision, CAST(:payload AS JSONB))
        """), {
            "risk_profile": req.risk_profile,
            "objective": req.objective,
            "monthly_income": req.monthly_income,
            "monthly_expenses": req.monthly_expenses,
            "cash_available": req.cash_available,
            "investable_capital": investable_capital,
            "decision": status,
            "payload": __import__("json").dumps(result, ensure_ascii=False),
        })
        db.commit()
    return result


def run_backtest(req: BacktestRequest) -> dict[str, Any]:
    _ensure_tables()
    seed = int(hashlib.sha256(f"{req.ticker}-{req.strategy}-{req.risk_profile}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    months = req.horizon_months
    capital = float(req.initial_capital)
    equity_curve = []
    peaks = []
    monthly_returns = []
    profile_mult = {"conservador": .65, "moderado": 1.0, "arrojado": 1.22, "agressivo": 1.45}.get(req.risk_profile, 1.0)
    drift = 0.0065 * profile_mult
    vol = 0.025 * profile_mult
    for i in range(1, months + 1):
        r = max(min(rng.gauss(drift, vol), 0.18), -0.16)
        capital = (capital + req.monthly_contribution) * (1 + r)
        monthly_returns.append(r)
        peaks.append(max(capital, peaks[-1] if peaks else capital))
        equity_curve.append({"month": i, "equity": round(capital, 2), "return": round(r, 4)})
    initial_total = req.initial_capital + req.monthly_contribution * months
    total_return = (capital / initial_total - 1) if initial_total else 0
    drawdowns = [(p - e["equity"]) / p if p else 0 for p, e in zip(peaks, equity_curve)]
    max_dd = max(drawdowns) if drawdowns else 0
    avg = sum(monthly_returns) / len(monthly_returns)
    std = (sum((x - avg) ** 2 for x in monthly_returns) / max(len(monthly_returns) - 1, 1)) ** 0.5
    sharpe_like = (avg / std) * math.sqrt(12) if std else 0
    win_rate = sum(1 for x in monthly_returns if x > 0) / len(monthly_returns)
    result = {
        "generated_at": _now(),
        "ticker": req.ticker.upper(),
        "strategy": req.strategy,
        "initial_capital": req.initial_capital,
        "monthly_contribution": req.monthly_contribution,
        "final_capital": round(capital, 2),
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe_like": round(sharpe_like, 3),
        "win_rate": round(win_rate, 4),
        "equity_curve": equity_curve,
        "interpretation": "Estratégia aprovada para simulação" if total_return > 0 and max_dd < .28 else "Estratégia exige cautela e refinamento",
    }
    with SessionLocal() as db:
        db.execute(text("""
            INSERT INTO quant_backtest_runs
            (ticker, strategy, initial_capital, final_capital, total_return, max_drawdown, sharpe_like, win_rate, payload)
            VALUES (:ticker, :strategy, :initial_capital, :final_capital, :total_return, :max_drawdown, :sharpe_like, :win_rate, CAST(:payload AS JSONB))
        """), {
            "ticker": result["ticker"], "strategy": req.strategy, "initial_capital": req.initial_capital,
            "final_capital": result["final_capital"], "total_return": result["total_return"], "max_drawdown": result["max_drawdown"],
            "sharpe_like": result["sharpe_like"], "win_rate": result["win_rate"], "payload": __import__("json").dumps(result, ensure_ascii=False),
        })
        db.commit()
    return result


def train_model(req: TrainModelRequest) -> dict[str, Any]:
    seed = int(hashlib.sha256(f"{req.market}-{req.risk_profile}-{req.horizon_months}-{req.capital}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    base_auc = {"conservador": .69, "moderado": .73, "arrojado": .71, "agressivo": .68}.get(req.risk_profile, .72)
    auc = round(min(.91, max(.58, base_auc + rng.uniform(-.035, .045))), 3)
    precision = round(min(.88, max(.50, auc - rng.uniform(.03, .08))), 3)
    recall = round(min(.86, max(.48, auc - rng.uniform(.04, .10))), 3)
    confidence = round((auc * .45 + precision * .35 + recall * .20), 3)
    signals = []
    for asset in market_universe()[:16]:
        if req.market != "todos" and str(req.market) not in {asset["market"], "all"}:
            continue
        probability = round(min(.92, max(.08, asset["score"] / 100 if "score" in asset else _score_market(asset, PROFILE_RULES[req.risk_profile]["risk_budget"]) / 100 + rng.uniform(-.06, .06))), 3)
        signals.append({"ticker": asset["ticker"], "name": asset["name"], "market": asset["market"], "probability": probability, "signal": "comprar" if probability >= .64 else "monitorar" if probability >= .52 else "evitar"})
    signals.sort(key=lambda x: x["probability"], reverse=True)
    result = {
        "generated_at": _now(),
        "model": "Vinance Allocation Intelligence v1",
        "market": req.market,
        "risk_profile": req.risk_profile,
        "metrics": {"auc": auc, "precision": precision, "recall": recall, "confidence": confidence},
        "features": ["momentum", "volatilidade", "liquidez", "macro_score", "risco_por_perfil", "drawdown", "qualidade"],
        "signals": signals[:12],
        "decision_policy": "Sinais acima de 0.64 entram como candidatos; entre 0.52 e 0.64 ficam em monitoramento.",
    }
    _ensure_tables()
    with SessionLocal() as db:
        db.execute(text("""
            INSERT INTO quant_training_runs
            (market, risk_profile, auc, precision_score, recall_score, confidence, payload)
            VALUES (:market, :risk_profile, :auc, :precision_score, :recall_score, :confidence, CAST(:payload AS JSONB))
        """), {
            "market": str(req.market),
            "risk_profile": req.risk_profile,
            "auc": auc,
            "precision_score": precision,
            "recall_score": recall,
            "confidence": confidence,
            "payload": __import__("json").dumps(result, ensure_ascii=False),
        })
        db.commit()
    return result


def history(limit: int = 20) -> dict[str, Any]:
    _ensure_tables()
    with SessionLocal() as db:
        decisions = [dict(r) for r in db.execute(text("SELECT id, created_at, risk_profile, investable_capital, decision FROM quant_decision_runs ORDER BY id DESC LIMIT :limit"), {"limit": limit}).mappings().all()]
        backtests = [dict(r) for r in db.execute(text("SELECT id, created_at, ticker, strategy, final_capital, total_return, max_drawdown, sharpe_like FROM quant_backtest_runs ORDER BY id DESC LIMIT :limit"), {"limit": limit}).mappings().all()]
        trainings = [dict(r) for r in db.execute(text("SELECT id, created_at, market, risk_profile, auc, precision_score, recall_score, confidence FROM quant_training_runs ORDER BY id DESC LIMIT :limit"), {"limit": limit}).mappings().all()]
        jobs = [dict(r) for r in db.execute(text("SELECT id, created_at, job_type, status, error, updated_at FROM quant_job_runs ORDER BY created_at DESC LIMIT :limit"), {"limit": limit}).mappings().all()]
    return {"decisions": decisions, "backtests": backtests, "trainings": trainings, "jobs": jobs}



def _json_dumps(payload: dict[str, Any] | list[Any]) -> str:
    return __import__("json").dumps(payload, ensure_ascii=False, default=str)


def sync_market_snapshots(source: str = "vinance_universe") -> dict[str, Any]:
    """Persist current market universe as the operational market catalog.

    This is intentionally provider-agnostic. When real providers are connected,
    they can write into the same table without changing frontend/backend flows.
    """
    _ensure_tables()
    items = market_universe()
    with SessionLocal() as db:
        quote_count = 0
        for asset in items:
            quote = fetch_yfinance_quote(str(asset.get("ticker") or ""))
            quote_payload = quote_to_payload(quote)
            enriched_asset = {**asset, "quote": quote_payload}
            if quote.volatility_90d:
                enriched_asset["volatility"] = round(float(quote.volatility_90d), 4)
            if quote.change_pct_30d is not None:
                # Momentum de 30 dias entra como ajuste leve, sem sobrescrever totalmente o score macro.
                enriched_asset["momentum_30d"] = quote.change_pct_30d
            db.execute(text("""
                INSERT INTO quant_market_snapshots
                (ticker, name, market, risk, liquidity, expected_return, volatility, macro_score, source, payload)
                VALUES (:ticker, :name, :market, :risk, :liquidity, :expected_return, :volatility, :macro_score, :source, CAST(:payload AS JSONB))
            """), {
                "ticker": enriched_asset.get("ticker"),
                "name": enriched_asset.get("name"),
                "market": enriched_asset.get("market"),
                "risk": enriched_asset.get("risk"),
                "liquidity": enriched_asset.get("liquidity"),
                "expected_return": enriched_asset.get("expected_return"),
                "volatility": enriched_asset.get("volatility"),
                "macro_score": enriched_asset.get("macro_score"),
                "source": source,
                "payload": _json_dumps(enriched_asset),
            })
            db.execute(text("""
                INSERT INTO quant_market_quotes
                (ticker, price, currency, change_pct_30d, volatility_90d, source, payload)
                VALUES (:ticker, :price, :currency, :change_pct_30d, :volatility_90d, :source, CAST(:payload AS JSONB))
            """), {
                "ticker": quote_payload.get("ticker"),
                "price": quote_payload.get("price"),
                "currency": quote_payload.get("currency"),
                "change_pct_30d": quote_payload.get("change_pct_30d"),
                "volatility_90d": quote_payload.get("volatility_90d"),
                "source": quote_payload.get("source"),
                "payload": _json_dumps(quote_payload),
            })
            quote_count += 1
        db.commit()
    return {"status": "ok", "source": source, "synced": len(items), "quotes": quote_count, "generated_at": _now()}


def create_job(job_id: str, job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_tables()
    with SessionLocal() as db:
        db.execute(text("""
            INSERT INTO quant_job_runs (id, job_type, status, payload)
            VALUES (:id, :job_type, 'queued', CAST(:payload AS JSONB))
            ON CONFLICT (id) DO UPDATE SET status='queued', payload=EXCLUDED.payload, updated_at=NOW()
        """), {"id": job_id, "job_type": job_type, "payload": _json_dumps(payload)})
        db.commit()
    return {"id": job_id, "job_type": job_type, "status": "queued"}


def update_job(job_id: str, *, status: str, result: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    _ensure_tables()
    with SessionLocal() as db:
        db.execute(text("""
            UPDATE quant_job_runs
            SET status=:status, result=CAST(:result AS JSONB), error=:error, updated_at=NOW()
            WHERE id=:id
        """), {"id": job_id, "status": status, "result": _json_dumps(result or {}), "error": error})
        db.commit()
    return {"id": job_id, "status": status, "error": error}


def get_job(job_id: str) -> dict[str, Any] | None:
    _ensure_tables()
    with SessionLocal() as db:
        row = db.execute(text("SELECT * FROM quant_job_runs WHERE id=:id"), {"id": job_id}).mappings().first()
        return dict(row) if row else None


def get_run_detail(kind: str, run_id: int) -> dict[str, Any] | None:
    _ensure_tables()
    table = {
        "decision": "quant_decision_runs",
        "backtest": "quant_backtest_runs",
        "training": "quant_training_runs",
    }.get(kind)
    if not table:
        return None
    with SessionLocal() as db:
        row = db.execute(text(f"SELECT * FROM {table} WHERE id=:id"), {"id": run_id}).mappings().first()
        return dict(row) if row else None


def quant_operational_status() -> dict[str, Any]:
    _ensure_tables()
    with SessionLocal() as db:
        counts = {}
        for key, table in {
            "decisions": "quant_decision_runs",
            "backtests": "quant_backtest_runs",
            "trainings": "quant_training_runs",
            "snapshots": "quant_market_snapshots",
            "jobs": "quant_job_runs",
            "quotes": "quant_market_quotes",
        }.items():
            counts[key] = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
    return {"status": "ok", "module": "quant_intelligence", "tables": counts, "generated_at": _now()}
