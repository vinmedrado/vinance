from backend.app.market.services.risk_engine import pct_return, volatility, max_drawdown, normalize

def classify(score: float):
    if score >= 80: return "Muito favorável"
    if score >= 65: return "Favorável"
    if score >= 45: return "Neutro"
    if score >= 30: return "Arriscado"
    return "Evitar"

def infer_asset_class(symbol: str, raw=None):
    s = symbol.upper(); name = str((raw or {}).get("longName") or (raw or {}).get("shortName") or "").lower()
    if s.endswith("11"):
        if "fii" in name or "fundo imobili" in name or "real estate" in name: return "fii"
        return "etf"
    if s.endswith("34") or s.endswith("35"): return "bdr"
    return "acoes"

def build_metrics_from_brapi(item: dict):
    prices = []
    for h in item.get("historicalDataPrice") or []:
        close = h.get("close") or h.get("adjClose")
        if close is not None: prices.append(float(close))
    current = item.get("regularMarketPrice")
    if current and (not prices or prices[-1] != current): prices.append(float(current))
    return {
        "return_30d": pct_return(prices, 30), "return_90d": pct_return(prices, 90),
        "return_180d": pct_return(prices, 180), "return_365d": pct_return(prices, 252),
        "volatility": volatility(prices), "drawdown": max_drawdown(prices), "momentum": pct_return(prices, 90),
        "liquidity": float(item.get("regularMarketVolume") or item.get("averageDailyVolume10Day") or 0),
        "dividend_yield": float(item.get("dividendYield")) if item.get("dividendYield") is not None else None,
        "pe_ratio": float(item.get("priceEarnings") or item.get("trailingPE")) if (item.get("priceEarnings") or item.get("trailingPE")) is not None else None,
        "price_to_book": float(item.get("priceToBook")) if item.get("priceToBook") is not None else None,
    }

def build_metrics_from_crypto(item: dict, prices: list[float]):
    return {
        "return_30d": (item.get("price_change_percentage_30d_in_currency") / 100) if item.get("price_change_percentage_30d_in_currency") is not None else pct_return(prices, 30),
        "return_90d": (item.get("price_change_percentage_90d_in_currency") / 100) if item.get("price_change_percentage_90d_in_currency") is not None else pct_return(prices, 90),
        "return_180d": pct_return(prices, 180),
        "return_365d": (item.get("price_change_percentage_1y_in_currency") / 100) if item.get("price_change_percentage_1y_in_currency") is not None else pct_return(prices, 365),
        "volatility": volatility(prices), "drawdown": max_drawdown(prices), "momentum": pct_return(prices, 90),
        "liquidity": float(item.get("total_volume") or 0), "dividend_yield": None, "pe_ratio": None, "price_to_book": None,
    }

def score_metrics(metrics: dict, asset_class: str, risk_profile: str, macro_context=None):
    ret_score = normalize(metrics.get("return_90d"), -0.20, 0.25)
    vol_score = normalize(metrics.get("volatility"), 0.05, 0.80, inverse=True)
    dd_score = normalize(metrics.get("drawdown"), -0.50, 0.0)
    mom_score = normalize(metrics.get("momentum"), -0.15, 0.20)
    liq_score = normalize(metrics.get("liquidity"), 0, 50_000_000)
    dy_score = normalize(metrics.get("dividend_yield"), 0, 0.12) if metrics.get("dividend_yield") is not None else 0.5
    if asset_class == "crypto": w = {"ret":.30,"vol":.25,"dd":.25,"mom":.15,"liq":.05,"dy":0}
    elif asset_class == "fii": w = {"ret":.20,"vol":.20,"dd":.20,"mom":.10,"liq":.10,"dy":.20}
    else: w = {"ret":.30,"vol":.20,"dd":.20,"mom":.15,"liq":.10,"dy":.05}
    raw = 100*(ret_score*w["ret"] + vol_score*w["vol"] + dd_score*w["dd"] + mom_score*w["mom"] + liq_score*w["liq"] + dy_score*w["dy"])
    if risk_profile == "Conservador" and asset_class == "crypto": raw -= 20
    if risk_profile == "Arrojado" and asset_class in ("acoes","etf","bdr","crypto"): raw += 5
    score = round(max(0, min(100, raw)), 2)
    return score, "Score educacional baseado em retorno ajustado ao risco, estabilidade, momentum, liquidez e dados disponíveis. Não é recomendação de compra."

def rank_opportunities(b3_quotes, crypto_items, crypto_price_map, risk_profile, macro_context=None):
    out = []
    for item in b3_quotes:
        symbol = item.get("symbol") or item.get("stock")
        if not symbol: continue
        ac = infer_asset_class(symbol, item); metrics = build_metrics_from_brapi(item); score, rat = score_metrics(metrics, ac, risk_profile, macro_context)
        out.append({"symbol": symbol, "asset_class": ac, "score": score, "classification": classify(score), "metrics": metrics, "rationale": rat})
    for item in crypto_items:
        coin_id = item.get("id"); symbol = (item.get("symbol") or coin_id or "crypto").upper()
        metrics = build_metrics_from_crypto(item, crypto_price_map.get(coin_id, [])); score, rat = score_metrics(metrics, "crypto", risk_profile, macro_context)
        out.append({"symbol": symbol, "asset_class": "crypto", "score": score, "classification": classify(score), "metrics": metrics, "rationale": rat})
    return sorted(out, key=lambda x: x["score"], reverse=True)
