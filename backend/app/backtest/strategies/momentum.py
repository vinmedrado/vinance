from typing import Any, Dict, List, Optional

from ._common import BaseSelectionStrategy, parse_metrics_json, safe_float


def _first_number(*values: Any, default: Optional[float] = None) -> Optional[float]:
    for value in values:
        parsed = safe_float(value, None)
        if parsed is not None:
            return parsed
    return default


class MomentumStrategy(BaseSelectionStrategy):
    """Estratégia momentum simples e operacional.

    Regras oficiais:
    - usa apenas ativos com preço acima da MM200;
    - usa apenas ativos com retorno_3m > 0;
    - score final = retorno_6m;
    - ordena por retorno_6m desc e seleciona top_n;
    - a execução continua sendo feita pelo StrategyBacktestRunner/rebalance existente.

    Observação prática:
    O Analysis Engine salva retornos em janelas de dias. Por isso:
    - retorno_3m é mapeado para retorno_90d;
    - retorno_6m é mapeado para retorno_180d.
    """

    name = 'momentum'

    def _mm200_status(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        distancia_mm200 = _first_number(metrics.get('distancia_mm200'))
        mm200 = _first_number(metrics.get('media_movel_200'))
        price = _first_number(
            metrics.get('close'),
            metrics.get('last_close'),
            metrics.get('price'),
            metrics.get('ultimo_preco'),
            metrics.get('preco'),
        )

        # O Analysis Engine calcula distancia_mm200 = last_close / mm200 - 1.
        # Se ela existe, é a forma mais robusta de validar price > mm200.
        if distancia_mm200 is not None:
            return {
                'above_mm200': distancia_mm200 > 0,
                'method': 'distancia_mm200',
                'distancia_mm200': distancia_mm200,
                'price': price,
                'media_movel_200': mm200,
            }

        # Fallback caso alguma versão salve preço junto no metrics_json.
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
            'distancia_mm200': distancia_mm200,
            'price': price,
            'media_movel_200': mm200,
        }

    def select(self, as_of_date: str) -> List[str]:
        rows = self.repository.get_strategy_universe(
            as_of_date,
            self.asset_class,
            self.tickers,
            mode=self.mode,
        )
        filtered = self._filter_rows(rows)

        ranked = []
        momentum_scores: Dict[str, Dict[str, Any]] = {}
        rejected = []
        metrics_found = 0

        for row in filtered:
            ticker = str(row.get('ticker') or '').upper().strip()
            if not ticker:
                continue

            metrics = parse_metrics_json(row.get('metrics') or row.get('metrics_json'))
            row['metrics'] = metrics
            if metrics:
                metrics_found += 1

            retorno_3m = _first_number(
                metrics.get('retorno_3m'),
                metrics.get('retorno_90d'),
            )
            retorno_6m = _first_number(
                metrics.get('retorno_6m'),
                metrics.get('retorno_180d'),
            )
            mm200 = self._mm200_status(metrics)

            info = {
                'retorno_3m': retorno_3m,
                'retorno_6m': retorno_6m,
                'score_final': retorno_6m,
                'mm200_status': mm200,
            }
            momentum_scores[ticker] = info

            if retorno_3m is None:
                rejected.append({'ticker': ticker, 'reason': 'sem retorno_3m/retorno_90d', **info})
                continue
            if retorno_3m <= 0:
                rejected.append({'ticker': ticker, 'reason': 'retorno_3m <= 0', **info})
                continue
            if retorno_6m is None:
                rejected.append({'ticker': ticker, 'reason': 'sem retorno_6m/retorno_180d', **info})
                continue
            if not mm200.get('above_mm200'):
                rejected.append({'ticker': ticker, 'reason': 'preço não está acima da MM200 ou MM200 ausente', **info})
                continue

            ranked.append((float(retorno_6m), ticker))

        ranked.sort(key=lambda item: item[0], reverse=True)
        selected = [ticker for _, ticker in ranked[: self.top_n]]

        self.last_diagnostics = {
            'strategy': self.name,
            'mode': self.mode,
            'scores_found': len(rows),
            'metrics_found': metrics_found,
            'source_used': 'asset_analysis_metrics' if metrics_found else None,
            'candidate_tickers': [str(r.get('ticker')) for r in filtered if r.get('ticker')],
            'selected_tickers': selected,
            # O runner já imprime factor_scores. Para manter compatibilidade, usamos essa chave.
            'factor_scores': momentum_scores,
            'momentum_scores': momentum_scores,
            'rejected': rejected[:50],
            'reason': None,
        }
        if not selected:
            self.last_diagnostics['reason'] = (
                'momentum não selecionou ativos: exige price > MM200, retorno_3m > 0 e retorno_6m disponível. '
                f'candidatos={len(filtered)}, metrics_found={metrics_found}, rejeitados={len(rejected)}.'
            )
        return selected
