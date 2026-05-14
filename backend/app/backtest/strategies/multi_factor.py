from typing import Any, Dict, List, Tuple

from ._common import BaseSelectionStrategy, clamp, parse_metrics_json, safe_float
from ..diversification import DiversificationPolicy, ticker_sector


def _score_from_return(value: Any) -> float:
    """Converte retorno decimal para escala 0-100.

    Ex.: 0.20 -> 70, -0.20 -> 30.
    """
    v = safe_float(value, None)
    if v is None:
        return 50.0
    return clamp(50.0 + (v * 100.0))


def _score_from_inverse_vol(value: Any) -> float:
    """Volatilidade menor é melhor. Aceita vol decimal ou percentual."""
    v = safe_float(value, None)
    if v is None:
        return 50.0
    # Se vier como percentual 25 em vez de 0.25, normaliza parcialmente.
    if v > 2:
        v = v / 100.0
    return clamp(100.0 - (v * 100.0))


def _score_from_dividend_yield(value: Any) -> float:
    v = safe_float(value, None)
    if v is None:
        return 0.0
    # DY costuma vir como decimal. 0.10 => 100; 0.06 => 60.
    if 0 <= v <= 1:
        return clamp(v * 1000.0)
    return clamp(v * 10.0 if v <= 20 else v)


def _score_from_trend(metrics: Dict[str, Any], row: Dict[str, Any]) -> float:
    fallback = safe_float(row.get('score_tendencia'), 50.0)
    values = []
    for key in ('distancia_mm20', 'distancia_mm50', 'distancia_mm200'):
        v = safe_float(metrics.get(key), None)
        if v is not None:
            # Distância decimal para escala: 0.10 => 60; -0.10 => 40.
            values.append(clamp(50.0 + v * 100.0))
    if values:
        return sum(values) / len(values)
    return float(fallback if fallback is not None else 50.0)


def _first_number(*values: Any, default: Any = None) -> Any:
    for value in values:
        parsed = safe_float(value, None)
        if parsed is not None:
            return parsed
    return default


def _mm200_status(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Retorna status de tendência usando MM200 quando disponível.

    O Analysis Engine geralmente salva distancia_mm200. Se não existir,
    tenta comparar preço/close com media_movel_200.
    """
    distancia = _first_number(metrics.get('distancia_mm200'))
    mm200 = _first_number(metrics.get('media_movel_200'))
    price = _first_number(
        metrics.get('close'),
        metrics.get('last_close'),
        metrics.get('price'),
        metrics.get('ultimo_preco'),
        metrics.get('preco'),
    )
    if distancia is not None:
        return {
            'above_mm200': distancia > 0,
            'method': 'distancia_mm200',
            'distancia_mm200': distancia,
            'price': price,
            'media_movel_200': mm200,
        }
    if price is not None and mm200 is not None and mm200 > 0:
        return {
            'above_mm200': price > mm200,
            'method': 'price_vs_mm200',
            'distancia_mm200': (price / mm200 - 1),
            'price': price,
            'media_movel_200': mm200,
        }
    return {
        'above_mm200': False,
        'method': 'missing_mm200',
        'distancia_mm200': distancia,
        'price': price,
        'media_movel_200': mm200,
    }


class DynamicSelectionPenalty:
    """PATCH 14 - penalização dinâmica para reduzir repetição de ativos.

    Não altera o score base. Calcula apenas um score_final para ordenação,
    usando frequência recente e cooldown de seleção consecutiva.
    """

    def __init__(self, memory_window: int = 6, penalty_factor: float = 4.0, cooldown_window: int = 3, cooldown_pct: float = 0.30):
        self.memory_window = max(1, int(memory_window or 6))
        self.penalty_factor = float(penalty_factor if penalty_factor is not None else 4.0)
        self.cooldown_window = max(1, int(cooldown_window or 3))
        self.cooldown_pct = float(cooldown_pct if cooldown_pct is not None else 0.30)
        self.history: List[List[str]] = []

    def recent_frequency(self, ticker: str) -> int:
        ticker = str(ticker or '').upper().strip()
        recent = self.history[-self.memory_window:]
        return sum(1 for selection in recent if ticker in selection)

    def consecutive_frequency(self, ticker: str) -> int:
        ticker = str(ticker or '').upper().strip()
        count = 0
        for selection in reversed(self.history):
            if ticker in selection:
                count += 1
            else:
                break
        return count

    def apply(self, ticker: str, original_score: float) -> Tuple[float, Dict[str, Any]]:
        frequency = self.recent_frequency(ticker)
        consecutive = self.consecutive_frequency(ticker)
        penalty = frequency * self.penalty_factor
        score_after_frequency = float(original_score) - penalty
        cooldown_applied = False
        cooldown_penalty = 0.0
        final_score = score_after_frequency
        if consecutive >= self.cooldown_window:
            cooldown_applied = True
            cooldown_penalty = score_after_frequency * self.cooldown_pct
            final_score = score_after_frequency * (1.0 - self.cooldown_pct)
        return clamp(final_score), {
            'score_original': float(original_score),
            'frequencia_recente': frequency,
            'penalidade_frequencia': penalty,
            'consecutivos': consecutive,
            'cooldown_aplicado': cooldown_applied,
            'cooldown_penalty': cooldown_penalty,
            'score_final': clamp(final_score),
        }

    def remember(self, selected: List[str]) -> None:
        cleaned = [str(t or '').upper().strip() for t in selected if str(t or '').strip()]
        self.history.append(cleaned)
        max_history = self.memory_window * 3
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]


class MultiFactorStrategy(BaseSelectionStrategy):
    name = 'multi_factor'

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.dynamic_penalty = DynamicSelectionPenalty(
            memory_window=int(self.params.get('selection_memory_window', 6) or 6),
            penalty_factor=float(self.params.get('selection_penalty_factor', 4.0) or 4.0),
            cooldown_window=int(self.params.get('selection_cooldown_window', 3) or 3),
            cooldown_pct=float(self.params.get('selection_cooldown_pct', 0.30) or 0.30),
        )

    def _metric_factor_score(self, row: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        metrics = parse_metrics_json(row.get('metrics') or row.get('metrics_json'))
        row['metrics'] = metrics

        weights = {
            'return': max(0.0, float(self.params.get('weight_return', 0.25))),
            'risk': max(0.0, float(self.params.get('weight_risk', 0.20))),
            'liquidity': max(0.0, float(self.params.get('weight_liquidity', 0.15))),
            'dividend': max(0.0, float(self.params.get('weight_dividend', 0.20))),
            'trend': max(0.0, float(self.params.get('weight_trend', 0.20))),
        }
        total_weight = sum(weights.values()) or 1.0

        retorno_base = (
            safe_float(metrics.get('retorno_180d'), None)
            if safe_float(metrics.get('retorno_180d'), None) is not None
            else safe_float(metrics.get('retorno_90d'), None)
        )
        return_score = _score_from_return(retorno_base)
        risk_score = safe_float(row.get('score_risco'), None)
        if risk_score is None:
            risk_score = _score_from_inverse_vol(metrics.get('volatilidade_90d'))
        liquidity_score = safe_float(row.get('score_liquidez'), None)
        if liquidity_score is None:
            liquidity_score = safe_float(metrics.get('liquidez_score'), 50.0)
        dividend_score = safe_float(row.get('score_dividendos'), None)
        if dividend_score is None:
            dividend_score = _score_from_dividend_yield(metrics.get('dividend_yield_12m'))
        trend_score = _score_from_trend(metrics, row)

        parts = {
            'return': clamp(return_score),
            'risk': clamp(risk_score),
            'liquidity': clamp(liquidity_score),
            'dividend': clamp(dividend_score),
            'trend': clamp(trend_score),
        }
        raw = sum(weights[k] * parts[k] for k in weights) / total_weight
        return clamp(raw), parts

    def _passes_mm200_filter(self, row: Dict[str, Any]) -> bool:
        # PATCH 12 RISCO: multi_factor agora sempre respeita tendência.
        # Só permite compra quando price > MM200. Quando o Analysis Engine não
        # disponibilizar preço bruto, usa distancia_mm200 > 0.
        metrics = parse_metrics_json(row.get('metrics') or row.get('metrics_json'))
        return bool(_mm200_status(metrics).get('above_mm200'))

    def _risk_filters(self, row: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        metrics = parse_metrics_json(row.get('metrics') or row.get('metrics_json'))
        retorno_3m = _first_number(metrics.get('retorno_3m'), metrics.get('retorno_90d'))
        mm200 = _mm200_status(metrics)
        details = {
            'retorno_3m': retorno_3m,
            'mm200_status': mm200,
        }
        if mm200.get('distancia_mm200') is not None and mm200.get('distancia_mm200') < -0.20:
            details['reason'] = 'distancia_mm200 < -20%'
            return False, details
        if retorno_3m is None:
            details['reason'] = 'retorno_3m/retorno_90d ausente'
            return False, details
        if retorno_3m < -0.15:
            details['reason'] = 'retorno_3m < -15%'
            return False, details
        return True, details

    def select(self, as_of_date: str) -> List[str]:
        # PATCH 10.1:
        # Em research, get_strategy_universe precisa receber mode='research' para
        # não aplicar filtro temporal e para usar o snapshot atual de asset_scores
        # + asset_analysis_metrics.
        rows = self.repository.get_strategy_universe(
            as_of_date,
            self.asset_class,
            self.tickers,
            mode=self.mode,
        )

        filtered = self._filter_rows(rows)
        metrics_found = sum(1 for row in filtered if parse_metrics_json(row.get('metrics') or row.get('metrics_json')))

        # PATCH 14 HOTFIX - o ranking precisa ser feito EXCLUSIVAMENTE pelo
        # score pós-penalização. O score base continua intacto para auditoria,
        # mas a seleção final usa final_score.
        ranked_assets: List[Dict[str, Any]] = []
        factor_scores: Dict[str, Dict[str, Any]] = {}
        rejected = []
        for row in filtered:
            ticker = str(row.get('ticker') or '').upper().strip()
            if not ticker:
                continue

            passed_risk, risk_details = self._risk_filters(row)
            if not passed_risk:
                rejected.append({'ticker': ticker, **risk_details})
                continue

            score_original, parts = self._metric_factor_score(row)
            final_score, penalty_details = self.dynamic_penalty.apply(ticker, score_original)
            penalty = float(penalty_details.get('penalidade_frequencia') or 0.0)
            frequency = int(penalty_details.get('frequencia_recente') or 0)
            ranked_row = {
                'ticker': ticker,
                'score_original': float(score_original),
                'penalty': penalty,
                'penalidade_aplicada': penalty,
                'final_score': float(final_score),
                'score_final': float(final_score),
                'frequencia_recente': frequency,
                'consecutivos': penalty_details.get('consecutivos'),
                'cooldown_aplicado': penalty_details.get('cooldown_aplicado'),
                'cooldown_penalty': penalty_details.get('cooldown_penalty'),
                **parts,
                'retorno_3m': risk_details.get('retorno_3m'),
                'mm200_status': risk_details.get('mm200_status'),
            }
            factor_scores[ticker] = dict(ranked_row)
            ranked_assets.append(ranked_row)

        ranked_assets.sort(key=lambda x: float(x.get('final_score') or -999999.0), reverse=True)
        ranked_tickers = [row['ticker'] for row in ranked_assets]

        # PATCH 13 - Diversificação: não altera o score, apenas limita concentração
        # na seleção final. Se o filtro setorial deixar poucos ativos, completa o
        # mínimo operacional com os próximos candidatos disponíveis.
        min_assets = min(max(3, self.top_n), 5)
        selected, diversification = DiversificationPolicy(max_per_sector=2, min_assets=min_assets).select(
            ranked_tickers,
            self.top_n,
        )

        for ticker in selected:
            factor_scores.setdefault(ticker, {})['sector'] = ticker_sector(ticker)

        penalty_summary = {
            ticker: {
                'ticker': ticker,
                'score_original': details.get('score_original'),
                'penalty': details.get('penalty'),
                'penalidade_aplicada': details.get('penalidade_aplicada', details.get('penalty')),
                'final_score': details.get('final_score'),
                'score_final': details.get('score_final'),
                'frequencia_recente': details.get('frequencia_recente'),
                'consecutivos': details.get('consecutivos'),
                'cooldown_aplicado': details.get('cooldown_aplicado'),
            }
            for ticker, details in factor_scores.items()
        }
        # PATCH 15.1: a memória da penalização dinâmica deve ser atualizada
        # no strategy_runner, depois da aplicação de hysteresis, usando a
        # seleção FINAL executada. O select() mantém apenas a seleção original.

        self.last_diagnostics = {
            'strategy': self.name,
            'mode': self.mode,
            'metrics_found': metrics_found,
            'scores_found': len(rows),
            'candidate_tickers': [str(r.get('ticker')) for r in filtered if r.get('ticker')],
            'selected_tickers': selected,
            'factor_scores': factor_scores,
            'diversification': diversification,
            'dynamic_selection_penalty': penalty_summary,
            'dynamic_ranked_candidates': ranked_assets[:50],
            'ranked_tickers': ranked_tickers,
            'ranking_sort_key': 'final_score',
            'selection_memory_window': self.dynamic_penalty.memory_window,
            'selection_penalty_factor': self.dynamic_penalty.penalty_factor,
            'selection_cooldown_window': self.dynamic_penalty.cooldown_window,
            'selection_cooldown_pct': self.dynamic_penalty.cooldown_pct,
            'excluded_by_sector_limit': diversification.get('excluded_by_sector_limit', []),
            'rejected': rejected[:20],
            'reason': None,
        }
        if not selected:
            self.last_diagnostics['reason'] = (
                'multi_factor não selecionou ativos: sem métricas/scores suficientes, filtros removeram candidatos '
                'ou filtros de risco bloquearam todos (price <= MM200, retorno_3m < -15% ou dados ausentes).'
            )
        return selected
