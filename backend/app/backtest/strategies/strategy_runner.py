import math
from typing import Any, Dict, List, Optional, Sequence

from ..backtest_repository import BacktestRepository
from ..backtest_engine import date_range, is_rebalance_day
from ..diagnostics import BacktestDiagnostics
from ..execution_simulator import ExecutionSimulator
from ..metrics import calculate_backtest_metrics
from ..portfolio_manager import PortfolioManager
from ..risk_manager import RiskManager
from . import get_strategy

VALID_MODES = {'no_lookahead', 'research'}
IRRELEVANT_SCORE_TOP_N_PARAMS = {
    'weight_return',
    'weight_risk',
    'weight_liquidity',
    'weight_dividend',
    'weight_trend',
    'require_above_mm200',
}


class StrategyBacktestRunner:
    """Runner genérico para estratégias do PATCH 10 com HOTFIX 10.1.

    - score_top_n mantém comportamento por asset_scores/asset_rankings.
    - multi_factor calcula seleção operacional usando asset_analysis_metrics.
    - mode=no_lookahead mantém filtro temporal.
    - mode=research usa snapshot atual para validar execução histórica.
    """

    def __init__(self, repository: Optional[BacktestRepository] = None):
        self.repository = repository or BacktestRepository()
        self.execution = ExecutionSimulator(self.repository)

    def run(
        self,
        strategy: str = 'score_top_n',
        asset_class: str = 'all',
        start_date: str = '2020-01-01',
        end_date: str = '2024-01-01',
        initial_capital: float = 10000.0,
        top_n: int = 10,
        rebalance_frequency: str = 'monthly',
        transaction_cost: float = 0.001,
        min_score: Optional[float] = None,
        max_position_pct: Optional[float] = None,
        min_liquidity_score: Optional[float] = None,
        tickers: Optional[Sequence[str]] = None,
        dry_run: bool = False,
        limit: Optional[int] = None,
        mode: str = 'no_lookahead',
        **strategy_params: Any,
    ) -> Dict[str, Any]:
        mode = str(mode or 'no_lookahead').strip().lower()
        if mode not in VALID_MODES:
            raise ValueError("mode inválido. Use 'no_lookahead' ou 'research'.")

        diagnostics = BacktestDiagnostics(enabled=True)
        if mode == 'research':
            diagnostics.warning('MODO RESEARCH: usa scores atuais sobre histórico. Não é backtest sem viés.')

        if strategy == 'score_top_n':
            ignored = {}
            for key in sorted(IRRELEVANT_SCORE_TOP_N_PARAMS):
                if key in strategy_params:
                    value = strategy_params.get(key)
                    # defaults do CLI não devem quebrar, mas também não podem ser aceitos silenciosamente.
                    if key == 'require_above_mm200':
                        if bool(value):
                            ignored[key] = value
                    elif value is not None:
                        ignored[key] = value
            if ignored:
                diagnostics.warning(
                    'Parâmetros ignorados: score_top_n usa asset_scores/asset_rankings e não aplica pesos/filtro MM200.',
                    strategy=strategy,
                    ignored_parameters=ignored,
                )

        strategy_cls = get_strategy(strategy)
        effective_top_n = max(1, min(int(top_n), int(limit))) if limit else max(1, int(top_n))
        risk = RiskManager(max_position_pct=float(max_position_pct or 0.15), cash_buffer_pct=0.10)

        selector = strategy_cls(
            self.repository,
            asset_class=asset_class,
            top_n=effective_top_n,
            min_score=min_score,
            tickers=tickers,
            min_liquidity_score=min_liquidity_score,
            mode=mode,
            **strategy_params,
        )

        portfolio = PortfolioManager(initial_capital, transaction_cost=transaction_cost)
        diagnostics.info(
            'Portfolio inicializado',
            initial_capital=initial_capital,
            cash=portfolio.cash,
            transaction_cost=transaction_cost,
        )
        diagnostics.info(
            'Controle de risco ativo',
            max_position_pct=risk.max_position_pct,
            cash_buffer_pct=risk.cash_buffer_pct,
            cash_buffer_value=initial_capital * risk.cash_buffer_pct,
        )
        diagnostics.info(
            'Controle de rebalance threshold ativo',
            rebalance_threshold_pct=float(strategy_params.get('rebalance_threshold_pct', 0.20) or 0.20),
        )
        diagnostics.info(
            'Controle de rebalance skip ativo',
            rebalance_skip_enabled=self._bool_param(strategy_params.get('rebalance_skip_enabled', True), True),
            rebalance_skip_max_changes=int(strategy_params.get('rebalance_skip_max_changes', 1) or 1),
        )

        params = {
            'strategy': strategy,
            'asset_class': asset_class,
            'top_n': effective_top_n,
            'rebalance_frequency': rebalance_frequency,
            'transaction_cost': transaction_cost,
            'min_score': min_score,
            'max_position_pct': float(max_position_pct or 0.15),
            'cash_buffer_pct': 0.10,
            'rebalance_threshold_pct': float(strategy_params.get('rebalance_threshold_pct', 0.20) or 0.20),
            'rebalance_skip_enabled': self._bool_param(strategy_params.get('rebalance_skip_enabled', True), True),
            'rebalance_skip_max_changes': int(strategy_params.get('rebalance_skip_max_changes', 1) or 1),
            'min_liquidity_score': min_liquidity_score,
            'mode': mode,
            **strategy_params,
        }

        backtest_id = 0
        if not dry_run:
            backtest_id = self.repository.create_run(
                strategy_name=strategy,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                **params,
            )

        previous_rebalance = None
        equity_curve: List[Dict[str, Any]] = []
        trades: List[Dict[str, Any]] = []
        skipped_events: List[Dict[str, Any]] = []
        holding_periods: Dict[str, int] = {}

        try:
            for current_date in date_range(start_date, end_date):
                if is_rebalance_day(current_date, rebalance_frequency, previous_rebalance):
                    selected_original = selector.select(current_date)
                    diag = getattr(selector, 'last_diagnostics', {}) or {}
                    selected_after_hysteresis, hysteresis_diag = self._apply_turnover_hysteresis(
                        selected_original=selected_original,
                        diagnostics_payload=diag,
                        current_positions=list(portfolio.positions.keys()),
                        holding_periods=holding_periods,
                        top_n=effective_top_n,
                        params=params,
                    )
                    selected, min_hold_diag = self._apply_min_hold(
                        selected_after_hysteresis=selected_after_hysteresis,
                        current_positions=list(portfolio.positions.keys()),
                        holding_periods=holding_periods,
                        params=params,
                    )
                    selected_before_skip = list(selected)
                    rebalance_skip_diag = self._apply_rebalance_skip(
                        current_positions=list(portfolio.positions.keys()),
                        selected_after_min_hold=selected_before_skip,
                        current_date=current_date,
                        strategy=strategy,
                        params=params,
                    )
                    if rebalance_skip_diag.get('skipped'):
                        selected = rebalance_skip_diag.get('selected_tickers_after_skip', selected)
                    previous_rebalance = current_date

                    # PATCH 15.1 + PATCH 16 + PATCH 18: alinhar a memória da penalização dinâmica
                    # com a carteira FINAL após hysteresis e MIN HOLD. Antes,
                    # multi_factor.select() memorizava selected_original; isso fazia a
                    # estratégia executar uma carteira e penalizar outra.
                    if hasattr(selector, 'dynamic_penalty') and hasattr(selector.dynamic_penalty, 'remember'):
                        try:
                            selector.dynamic_penalty.remember(selected)
                            diagnostics.info(
                                'Memória da penalização dinâmica atualizada após hysteresis/min_hold',
                                date=current_date,
                                strategy=strategy,
                                selected_tickers_after_hysteresis=selected_after_hysteresis,
                                selected_tickers_after_min_hold=selected_before_skip,
                                selected_tickers_after_rebalance_skip=selected,
                                selected_tickers_original=selected_original,
                            )
                        except Exception as exc:
                            diagnostics.warning(
                                'Falha ao atualizar memória da penalização dinâmica',
                                date=current_date,
                                strategy=strategy,
                                error=str(exc),
                            )

                    selected_set = set(selected)

                    diagnostics.info(
                        'Rebalanceamento iniciado',
                        date=current_date,
                        strategy=strategy,
                        mode=mode,
                        scores_found=diag.get('scores_found', 0),
                        rankings_found=diag.get('rankings_found', 0),
                        metrics_found=diag.get('metrics_found', 0),
                        source_used=diag.get('source_used'),
                        scores_total_db=diag.get('scores_total_db'),
                        scores_after_filter=diag.get('scores_after_filter'),
                        factor_scores=diag.get('factor_scores'),
                        dynamic_selection_penalty=diag.get('dynamic_selection_penalty'),
                        dynamic_ranked_candidates=diag.get('dynamic_ranked_candidates'),
                        ranking_sort_key=diag.get('ranking_sort_key'),
                        selection_memory_window=diag.get('selection_memory_window'),
                        selection_penalty_factor=diag.get('selection_penalty_factor'),
                        candidate_tickers=diag.get('candidate_tickers', []),
                        selected_tickers_original=selected_original,
                        selected_tickers_after_hysteresis=selected_after_hysteresis,
                        selected_tickers_after_min_hold=selected_before_skip,
                        selected_tickers_after_rebalance_skip=selected,
                        selected_tickers=selected,
                        turnover_control=hysteresis_diag,
                        min_hold_control=min_hold_diag,
                        rebalance_skip_control=rebalance_skip_diag,
                        diversification=diag.get('diversification'),
                    )
                    diagnostics.info(
                        'Controle de turnover/hysteresis aplicado',
                        date=current_date,
                        strategy=strategy,
                        selected_tickers_original=selected_original,
                        selected_tickers_after_hysteresis=selected_after_hysteresis,
                        selected_tickers_after_min_hold=selected,
                        hysteresis_buffer=hysteresis_diag.get('hysteresis_buffer'),
                        min_holding_period_rebalances=hysteresis_diag.get('min_holding_period_rebalances'),
                        kept_by_hysteresis=hysteresis_diag.get('kept_by_hysteresis'),
                        sold_by_rank_exit=hysteresis_diag.get('sold_by_rank_exit'),
                        turnover_estimated_before=hysteresis_diag.get('turnover_estimated_before'),
                        turnover_estimated_after=hysteresis_diag.get('turnover_estimated_after'),
                    )
                    diagnostics.info(
                        'Controle MIN HOLD aplicado',
                        date=current_date,
                        strategy=strategy,
                        min_holding_period_rebalances=min_hold_diag.get('min_holding_period_rebalances'),
                        holding_periods=min_hold_diag.get('holding_periods'),
                        min_hold_blocked=min_hold_diag.get('min_hold_blocked'),
                        sold_normally=min_hold_diag.get('sold_normally'),
                        selected_tickers_after_hysteresis=selected_after_hysteresis,
                        selected_tickers_after_min_hold=selected_before_skip,
                        turnover_estimated_before_min_hold=min_hold_diag.get('turnover_estimated_before_min_hold'),
                        turnover_estimated_after_min_hold=min_hold_diag.get('turnover_estimated_after_min_hold'),
                    )
                    diagnostics.info(
                        'Controle REBALANCE SKIP aplicado',
                        date=current_date,
                        strategy=strategy,
                        current_tickers=rebalance_skip_diag.get('current_tickers'),
                        selected_tickers_after_hysteresis_min_hold=rebalance_skip_diag.get('selected_tickers_after_hysteresis_min_hold'),
                        selected_tickers_after_rebalance_skip=rebalance_skip_diag.get('selected_tickers_after_skip'),
                        added=rebalance_skip_diag.get('added'),
                        removed=rebalance_skip_diag.get('removed'),
                        total_changes=rebalance_skip_diag.get('total_changes'),
                        rebalance_skip_enabled=rebalance_skip_diag.get('enabled'),
                        rebalance_skip_max_changes=rebalance_skip_diag.get('rebalance_skip_max_changes'),
                        skipped=rebalance_skip_diag.get('skipped'),
                        reason=rebalance_skip_diag.get('reason'),
                    )

                    if diag.get('excluded_by_sector_limit'):
                        diagnostics.info(
                            'Ativos excluídos por limite setorial',
                            date=current_date,
                            strategy=strategy,
                            excluded=diag.get('excluded_by_sector_limit', [])[:30],
                        )
                    if diag.get('rejected'):
                        diagnostics.info(
                            'Ativos filtrados pelo controle de risco/estratégia',
                            date=current_date,
                            strategy=strategy,
                            rejected=diag.get('rejected', [])[:20],
                        )

                    if not selected:
                        reason = diag.get('reason') or 'Estratégia não encontrou candidatos válidos para os filtros/parâmetros.'
                        skipped_events.append({'date': current_date, 'ticker': None, 'reason': reason})
                        diagnostics.warning('Nenhum ativo selecionado', date=current_date, strategy=strategy, reason=reason)

                    orders_generated = 0
                    orders_executed = 0

                    if rebalance_skip_diag.get('skipped'):
                        diagnostics.info(
                            'Rebalanceamento ignorado por baixa mudança na seleção',
                            date=current_date,
                            strategy=strategy,
                            current_tickers=rebalance_skip_diag.get('current_tickers'),
                            selected_tickers=rebalance_skip_diag.get('selected_tickers_after_hysteresis_min_hold'),
                            added=rebalance_skip_diag.get('added'),
                            removed=rebalance_skip_diag.get('removed'),
                            total_changes=rebalance_skip_diag.get('total_changes'),
                            rebalance_skip_max_changes=rebalance_skip_diag.get('rebalance_skip_max_changes'),
                            reason='rebalance_skip',
                        )
                    else:
                        # HOTFIX 10.1 mantém a lógica 9.5: rebalanceamento completo.
                        # 1) busca preço D+1 de todos os selecionados + posições atuais;
                        # 2) calcula delta em relação ao alvo;
                        # 3) executa todas as vendas;
                        # 4) executa compras com cash atualizado.
                        execution_prices: Dict[str, tuple] = {}
                        universe_for_execution = sorted(set(selected) | set(portfolio.positions.keys()))
                        for ticker in universe_for_execution:
                            execution = self.execution.next_close(ticker, current_date)
                            if not execution:
                                reason = 'sem preco D+1 para rebalanceamento'
                                skipped_events.append({'date': current_date, 'ticker': ticker, 'reason': reason})
                                diagnostics.warning('Preço de execução não encontrado', date=current_date, ticker=ticker, reason=reason)
                                continue
                            exec_date, price = execution
                            if not risk.is_price_valid(price):
                                reason = 'preco invalido para rebalanceamento'
                                skipped_events.append({'date': current_date, 'ticker': ticker, 'reason': reason})
                                diagnostics.warning('Preço inválido no rebalanceamento', date=current_date, ticker=ticker, exec_date=exec_date, price=price, reason=reason)
                                continue
                            execution_prices[ticker] = (exec_date, float(price))
                            diagnostics.info('Preço de execução encontrado', signal_date=current_date, exec_date=exec_date, ticker=ticker, price=price, action='rebalance')

                        valuation_prices = {ticker: price for ticker, (_, price) in execution_prices.items()}
                        equity = portfolio.total_value(valuation_prices)
                        selected_count = len(selected)
                        target_value = risk.target_value(equity, selected_count)
                        concentration_total = sum(
                            portfolio.position_value(t, valuation_prices.get(t, 0.0)) for t in portfolio.positions
                        ) / equity if equity else 0.0
                        diagnostics.info(
                            'Target allocation calculado',
                            date=current_date,
                            selected_count=selected_count,
                            equity=equity,
                            target_value_per_asset=target_value,
                            max_position_pct=risk.max_position_pct,
                            cash_buffer_pct=risk.cash_buffer_pct,
                            target_cash_buffer=equity * risk.cash_buffer_pct,
                            concentration_total=concentration_total,
                            cash=portfolio.cash,
                        )

                        rebalance_plan: List[Dict[str, Any]] = []
                        for ticker in universe_for_execution:
                            if ticker not in execution_prices:
                                continue
                            exec_date, price = execution_prices[ticker]
                            current_value = portfolio.position_value(ticker, price)
                            target_for_ticker = target_value if ticker in selected_set else 0.0
                            delta = target_for_ticker - current_value
                            action = 'hold'
                            quantity = 0
                            if delta > 0:
                                quantity = int(math.floor(delta / price))
                                action = 'buy' if quantity > 0 else 'skip_buy_quantity_zero'
                            elif delta < 0:
                                quantity = int(math.floor(abs(delta) / price))
                                action = 'sell' if quantity > 0 else 'skip_sell_quantity_zero'

                            # PATCH 17: evitar micro-ajustes. Nao bloqueia compra inicial
                            # nem venda total obrigatoria; aplica apenas ajuste parcial.
                            rebalance_threshold_pct = float(params.get('rebalance_threshold_pct', 0.20) or 0.20)
                            base_value = max(float(current_value), float(target_for_ticker), 1.0)
                            delta_pct = abs(float(delta)) / base_value
                            is_initial_buy = current_value <= 0 and target_for_ticker > 0
                            is_forced_full_sell = target_for_ticker <= 0 and current_value > 0 and ticker not in selected_set
                            is_partial_adjustment = (
                                ticker in selected_set
                                and current_value > 0
                                and target_for_ticker > 0
                                and action in {'buy', 'sell'}
                            )
                            if is_partial_adjustment and delta_pct < rebalance_threshold_pct:
                                diagnostics.info(
                                    'Ordem ignorada por rebalance_threshold',
                                    date=current_date,
                                    ticker=ticker,
                                    current_value=current_value,
                                    target_value=target_for_ticker,
                                    delta=delta,
                                    delta_pct=delta_pct,
                                    rebalance_threshold_pct=rebalance_threshold_pct,
                                    operation_original=action,
                                    operation='skip_rebalance_threshold',
                                    reason='rebalance_threshold',
                                )
                                action = 'skip_rebalance_threshold'
                                quantity = 0

                            row = {
                                'ticker': ticker,
                                'exec_date': exec_date,
                                'price': price,
                                'current_value': current_value,
                                'target_value': target_for_ticker,
                                'delta': delta,
                                'action': action,
                                'quantity': quantity,
                                'delta_pct': delta_pct,
                                'rebalance_threshold_pct': rebalance_threshold_pct,
                                'is_initial_buy': is_initial_buy,
                                'is_forced_full_sell': is_forced_full_sell,
                            }
                            rebalance_plan.append(row)
                            diagnostics.info(
                                'Delta de rebalanceamento calculado',
                                date=current_date,
                                ticker=ticker,
                                price=price,
                                current_value=current_value,
                                target_value=target_for_ticker,
                                delta=delta,
                                delta_pct=delta_pct,
                                rebalance_threshold_pct=rebalance_threshold_pct,
                                allocation_pct=(current_value / equity if equity else 0.0),
                                target_allocation_pct=(target_for_ticker / equity if equity else 0.0),
                                max_position_pct=risk.max_position_pct,
                                above_position_limit=(current_value / equity if equity else 0.0) > risk.max_position_pct,
                                operation=action,
                                quantity=quantity,
                                cash=portfolio.cash,
                            )

                        threshold_skipped = [x for x in rebalance_plan if x['action'] == 'skip_rebalance_threshold']
                        if threshold_skipped:
                            diagnostics.info(
                                'Resumo rebalance_threshold',
                                date=current_date,
                                strategy=strategy,
                                rebalance_threshold_pct=float(params.get('rebalance_threshold_pct', 0.20) or 0.20),
                                skipped_count=len(threshold_skipped),
                                skipped_tickers=[x['ticker'] for x in threshold_skipped],
                            )

                        # VENDAS PRIMEIRO
                        for order in [x for x in rebalance_plan if x['action'] == 'sell']:
                            orders_generated += 1
                            cash_before = portfolio.cash
                            trade = portfolio.sell_quantity(
                                order['ticker'],
                                order['price'],
                                order['quantity'],
                                order['exec_date'],
                                target_value=order['target_value'],
                                delta=order['delta'],
                            )
                            if trade:
                                orders_executed += 1
                                trades.append(trade)
                                diagnostics.info(
                                    'Ordem executada',
                                    operation='sell',
                                    ticker=trade.get('ticker'),
                                    date=trade.get('date'),
                                    price=trade.get('price'),
                                    quantity=trade.get('quantity'),
                                    gross_value=trade.get('gross_value'),
                                    transaction_cost=trade.get('transaction_cost'),
                                    net_value=trade.get('net_value'),
                                    cash_before=cash_before,
                                    cash_after=portfolio.cash,
                                    delta=order['delta'],
                                )
                                if not dry_run:
                                    self.repository.insert_trade(backtest_id, trade)
                            else:
                                reject = portfolio.last_reject_reason or {}
                                reason = reject.get('reason') or 'portfolio não executou venda'
                                skipped_events.append({'date': current_date, 'ticker': order['ticker'], 'reason': reason})
                                diagnostics.warning('Ordem de venda não executada', date=current_date, ticker=order['ticker'], reason=reason, order=order, reject=reject)

                        # COMPRAS DEPOIS
                        for order in [x for x in rebalance_plan if x['action'] == 'buy']:
                            orders_generated += 1
                            buy_value = order['quantity'] * order['price']
                            preview = portfolio.preview_buy_to_value(order['ticker'], order['price'], buy_value)
                            diagnostics.info(
                                'Sizing de compra calculado',
                                date=current_date,
                                ticker=order['ticker'],
                                price=order['price'],
                                delta=order['delta'],
                                target_value=order['target_value'],
                                quantity=preview.get('quantity'),
                                buy_value=preview.get('buy_value'),
                                transaction_cost=preview.get('transaction_cost'),
                                total_cost=preview.get('total_cost'),
                                cash_before=preview.get('cash_before'),
                                cash_after_estimated=preview.get('cash_after_estimated'),
                                can_execute=preview.get('can_execute'),
                                reason=preview.get('reason'),
                            )
                            cash_before = portfolio.cash
                            trade = portfolio.buy_to_value(order['ticker'], order['price'], buy_value, order['exec_date'])
                            if trade:
                                orders_executed += 1
                                trades.append(trade)
                                diagnostics.info(
                                    'Ordem executada',
                                    operation='buy',
                                    ticker=trade.get('ticker'),
                                    date=trade.get('date'),
                                    price=trade.get('price'),
                                    quantity=trade.get('quantity'),
                                    gross_value=trade.get('gross_value'),
                                    transaction_cost=trade.get('transaction_cost'),
                                    net_value=trade.get('net_value'),
                                    cash_before=cash_before,
                                    cash_after=portfolio.cash,
                                    delta=order['delta'],
                                )
                                if not dry_run:
                                    self.repository.insert_trade(backtest_id, trade)
                            else:
                                reject = portfolio.last_reject_reason or preview
                                reason = reject.get('reason') or 'portfolio não executou compra'
                                skipped_events.append({'date': current_date, 'ticker': order['ticker'], 'reason': reason})
                                diagnostics.warning(
                                    'Ordem de compra não executada',
                                    date=current_date,
                                    ticker=order['ticker'],
                                    reason=reason,
                                    order=order,
                                    reject=reject,
                                    cash=portfolio.cash,
                                )

                    diagnostics.info(
                        'Rebalanceamento finalizado',
                        date=current_date,
                        strategy=strategy,
                        orders_generated=orders_generated,
                        orders_executed=orders_executed,
                        cash=portfolio.cash,
                    )

                    active_position_tickers = set(portfolio.positions.keys())
                    for held_ticker in list(holding_periods.keys()):
                        if held_ticker not in active_position_tickers:
                            holding_periods.pop(held_ticker, None)
                    for held_ticker in active_position_tickers:
                        holding_periods[held_ticker] = holding_periods.get(held_ticker, 0) + 1
                    diagnostics.info(
                        'Período de manutenção atualizado',
                        date=current_date,
                        holding_periods=dict(sorted(holding_periods.items())),
                    )

                price_map = self._current_prices(list(portfolio.positions.keys()), current_date)
                positions_value = portfolio.positions_value(price_map)
                equity_value = portfolio.cash + positions_value
                curve_row = {
                    'date': current_date,
                    'equity_value': equity_value,
                    'cash': portfolio.cash,
                    'positions_value': positions_value,
                }
                equity_curve.append(curve_row)

                if not dry_run:
                    self.repository.insert_equity(backtest_id, current_date, equity_value, portfolio.cash, positions_value)
                    for ticker, pos in portfolio.positions.items():
                        self.repository.upsert_position(backtest_id, ticker, pos.quantity, pos.avg_price, price_map.get(ticker), current_date)

            metrics = calculate_backtest_metrics(equity_curve, trades, initial_capital)
            metrics.update({'backtest_id': backtest_id, 'strategy': strategy, 'skipped_events': len(skipped_events), 'mode': mode})
            if not dry_run:
                self.repository.insert_metrics(backtest_id, metrics)
                self.repository.finish_run(backtest_id, 'success')
                self.repository.commit()

            diagnostics.info('Backtest de estratégia finalizado', backtest_id=backtest_id, strategy=strategy, trades=len(trades), skipped_events=len(skipped_events), metrics=metrics)
            return {
                'backtest_id': backtest_id,
                'strategy': strategy,
                'metrics': metrics,
                'trades': len(trades),
                'skipped_events': skipped_events[:50],
                'diagnostics': diagnostics.events[:300],
                'dry_run': dry_run,
                'mode': mode,
                'parameters': params,
            }

        except Exception as exc:
            diagnostics.error('Backtest de estratégia falhou', error=str(exc))
            if not dry_run and backtest_id:
                self.repository.finish_run(backtest_id, 'failed', str(exc))
            raise

    def _bool_param(self, value: Any, default: bool = True) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() not in {'0', 'false', 'no', 'n', 'off'}

    def _apply_turnover_hysteresis(
        self,
        selected_original: Sequence[str],
        diagnostics_payload: Dict[str, Any],
        current_positions: Sequence[str],
        holding_periods: Dict[str, int],
        top_n: int,
        params: Dict[str, Any],
    ) -> tuple[List[str], Dict[str, Any]]:
        """PATCH 15: trava anti-turnover/hysteresis.

        Não altera score, final_score, filtros de risco ou diversificação.
        Apenas evita vender ativo já carregado quando ele ainda está bem ranqueado
        dentro de top_n + hysteresis_buffer, ou quando ainda não cumpriu o período
        mínimo de manutenção e continua no universo ranqueado.
        """
        original = [str(t or '').upper().strip() for t in selected_original if str(t or '').strip()]
        current = [str(t or '').upper().strip() for t in current_positions if str(t or '').strip()]

        enabled = self._bool_param(params.get('turnover_control_enabled', True), True)
        buffer_size = max(0, int(params.get('hysteresis_buffer', 2) or 0))
        min_holding = max(0, int(params.get('min_holding_period_rebalances', 2) or 0))
        max_selected = max(1, int(top_n or len(original) or 1))

        ranked_tickers = diagnostics_payload.get('ranked_tickers') or []
        if not ranked_tickers:
            ranked_candidates = diagnostics_payload.get('dynamic_ranked_candidates') or []
            ranked_tickers = [str(r.get('ticker') or '').upper().strip() for r in ranked_candidates if isinstance(r, dict) and r.get('ticker')]
        ranked_tickers = [str(t or '').upper().strip() for t in ranked_tickers if str(t or '').strip()]
        rank_position = {ticker: idx + 1 for idx, ticker in enumerate(ranked_tickers)}
        allowed_rank = max_selected + buffer_size
        retainable = set(ranked_tickers[:allowed_rank]) if ranked_tickers else set(original)

        if not enabled:
            return original[:max_selected], {
                'enabled': False,
                'hysteresis_buffer': buffer_size,
                'min_holding_period_rebalances': min_holding,
                'selected_tickers_original': original,
                'selected_tickers_after_hysteresis': original[:max_selected],
                'kept_by_hysteresis': [],
                'sold_by_rank_exit': [t for t in current if t not in set(original)],
                'turnover_estimated_before': len(set(current) ^ set(original)),
                'turnover_estimated_after': len(set(current) ^ set(original[:max_selected])),
                'reason': 'turnover_control_disabled',
            }

        kept_by_hysteresis: List[Dict[str, Any]] = []
        sold_by_rank_exit: List[Dict[str, Any]] = []
        retained: List[str] = []
        original_set = set(original)

        for ticker in current:
            rank = rank_position.get(ticker)
            holding_age = int(holding_periods.get(ticker, 0) or 0)
            keep_reason = None
            if ticker in original_set:
                keep_reason = 'already_in_selected_original'
            elif ticker in retainable:
                keep_reason = 'inside_top_n_plus_hysteresis_buffer'
            elif min_holding > 0 and holding_age < min_holding and ticker in rank_position:
                keep_reason = 'below_min_holding_period_but_still_ranked'

            if keep_reason:
                retained.append(ticker)
                if ticker not in original_set:
                    kept_by_hysteresis.append({
                        'ticker': ticker,
                        'rank': rank,
                        'holding_period_rebalances': holding_age,
                        'reason': keep_reason,
                    })
            else:
                sold_by_rank_exit.append({
                    'ticker': ticker,
                    'rank': rank,
                    'holding_period_rebalances': holding_age,
                    'reason': 'outside_hysteresis_buffer_or_removed_by_risk_filters',
                })

        # Retidos primeiro para evitar giro; depois completa com melhores novos candidatos.
        final_selection: List[str] = []
        for ticker in retained:
            if ticker not in final_selection:
                final_selection.append(ticker)
        for ticker in original:
            if ticker not in final_selection:
                final_selection.append(ticker)
            if len(final_selection) >= max_selected:
                break

        if len(final_selection) > max_selected:
            final_selection = sorted(
                final_selection,
                key=lambda t: rank_position.get(t, 10**9),
            )[:max_selected]

        before_turnover = len(set(current) ^ set(original))
        after_turnover = len(set(current) ^ set(final_selection))
        return final_selection, {
            'enabled': True,
            'hysteresis_buffer': buffer_size,
            'allowed_rank_to_keep': allowed_rank,
            'min_holding_period_rebalances': min_holding,
            'selected_tickers_original': original,
            'selected_tickers_after_hysteresis': final_selection,
            'kept_by_hysteresis': kept_by_hysteresis,
            'sold_by_rank_exit': sold_by_rank_exit,
            'current_positions': current,
            'turnover_estimated_before': before_turnover,
            'turnover_estimated_after': after_turnover,
            'turnover_reduction_estimated': before_turnover - after_turnover,
        }

    def _apply_min_hold(
        self,
        selected_after_hysteresis: Sequence[str],
        current_positions: Sequence[str],
        holding_periods: Dict[str, int],
        params: Dict[str, Any],
    ) -> tuple[List[str], Dict[str, Any]]:
        """PATCH 16: tempo mínimo de permanência após hysteresis.

        Atua apenas na seleção final executável. Se um ativo já está na
        carteira e ainda não cumpriu min_holding_period_rebalances, ele não
        pode ser vendido neste rebalanceamento. Isso reduz turnover sem alterar
        score, final_score, filtros, diversificação, banco ou execução.
        """
        selected = [str(t or '').upper().strip() for t in selected_after_hysteresis if str(t or '').strip()]
        current = [str(t or '').upper().strip() for t in current_positions if str(t or '').strip()]
        selected_set = set(selected)
        min_hold = max(0, int(params.get('min_holding_period_rebalances', 2) or 0))

        before_turnover = len(set(current) ^ selected_set)
        min_hold_blocked: List[Dict[str, Any]] = []
        sold_normally: List[Dict[str, Any]] = []
        final_selection = list(selected)

        for ticker in current:
            holding_age = int(holding_periods.get(ticker, 0) or 0)
            if ticker not in selected_set:
                if min_hold > 0 and holding_age < min_hold:
                    final_selection.append(ticker)
                    selected_set.add(ticker)
                    min_hold_blocked.append({
                        'ticker': ticker,
                        'holding_period_rebalances': holding_age,
                        'min_holding_period_rebalances': min_hold,
                        'reason': 'blocked_sell_below_min_holding_period',
                    })
                else:
                    sold_normally.append({
                        'ticker': ticker,
                        'holding_period_rebalances': holding_age,
                        'min_holding_period_rebalances': min_hold,
                        'reason': 'eligible_to_sell_after_min_hold',
                    })

        after_turnover = len(set(current) ^ set(final_selection))
        return final_selection, {
            'enabled': min_hold > 0,
            'min_holding_period_rebalances': min_hold,
            'holding_periods': {ticker: int(holding_periods.get(ticker, 0) or 0) for ticker in current},
            'min_hold_blocked': min_hold_blocked,
            'sold_normally': sold_normally,
            'selected_tickers_after_hysteresis': selected,
            'selected_tickers_after_min_hold': final_selection,
            'turnover_estimated_before_min_hold': before_turnover,
            'turnover_estimated_after_min_hold': after_turnover,
            'turnover_reduction_estimated_min_hold': before_turnover - after_turnover,
        }

    def _apply_rebalance_skip(
        self,
        current_positions: Sequence[str],
        selected_after_min_hold: Sequence[str],
        current_date: str,
        strategy: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """PATCH 18: evita rebalanceamento mensal desnecessário.

        Se a carteira atual e a seleção final após hysteresis + min hold são
        praticamente iguais, não gera ordens naquele rebalanceamento. Isso atua
        antes do rebalance_threshold e não altera score, final_score, filtros,
        diversificação, hysteresis, min hold, banco ou win rate.
        """
        enabled = self._bool_param(params.get('rebalance_skip_enabled', True), True)
        max_changes = max(0, int(params.get('rebalance_skip_max_changes', 1) or 0))
        current = sorted({str(t or '').upper().strip() for t in current_positions if str(t or '').strip()})
        selected = [str(t or '').upper().strip() for t in selected_after_min_hold if str(t or '').strip()]
        selected_unique = []
        for ticker in selected:
            if ticker not in selected_unique:
                selected_unique.append(ticker)
        selected_set = set(selected_unique)
        current_set = set(current)
        added = sorted(selected_set - current_set)
        removed = sorted(current_set - selected_set)
        total_changes = len(added) + len(removed)

        result = {
            'enabled': enabled,
            'skipped': False,
            'current_tickers': current,
            'selected_tickers_after_hysteresis_min_hold': selected_unique,
            'selected_tickers_after_skip': selected_unique,
            'added': added,
            'removed': removed,
            'total_changes': total_changes,
            'rebalance_skip_max_changes': max_changes,
            'reason': None,
        }

        if not enabled:
            result['reason'] = 'rebalance_skip_disabled'
            return result
        if not current:
            result['reason'] = 'first_rebalance_portfolio_empty'
            return result
        if total_changes > max_changes:
            result['reason'] = 'changes_above_threshold'
            return result

        # Segurança: se algum ativo atual não tiver preço D+1 válido, não pula.
        # Assim o rebalanceamento normal pode lidar com preço ausente/inválido.
        missing_current_prices = []
        invalid_current_prices = []
        for ticker in current:
            execution = self.execution.next_close(ticker, current_date)
            if not execution:
                missing_current_prices.append(ticker)
                continue
            _, price = execution
            if price is None or float(price) <= 0:
                invalid_current_prices.append({'ticker': ticker, 'price': price})
        if missing_current_prices or invalid_current_prices:
            result['reason'] = 'current_position_without_valid_execution_price'
            result['missing_current_prices'] = missing_current_prices
            result['invalid_current_prices'] = invalid_current_prices
            return result

        # Se há venda real sugerida dentro do limite tolerado, isso é exatamente
        # o caso de baixa mudança que queremos evitar: manter a carteira atual.
        result['skipped'] = True
        result['selected_tickers_after_skip'] = current
        result['reason'] = 'rebalance_skip'
        return result

    def _current_prices(self, tickers: Sequence[str], as_of_date: str) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        for ticker in tickers:
            price = self.repository.get_close_on_or_before(ticker, as_of_date)
            if price is not None:
                prices[ticker] = price
        return prices
