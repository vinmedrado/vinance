import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence

from .backtest_repository import BacktestRepository
from .diagnostics import BacktestDiagnostics
from .execution_simulator import ExecutionSimulator
from .metrics import calculate_backtest_metrics
from .portfolio_manager import PortfolioManager
from .risk_manager import RiskManager
from .strategy_score_top_n import StrategyScoreTopN

VALID_MODES = {'no_lookahead', 'research'}


def parse_date(value: str) -> datetime:
    return datetime.strptime(value[:10], '%Y-%m-%d')


def date_range(start_date: str, end_date: str):
    current = parse_date(start_date)
    end = parse_date(end_date)
    while current <= end:
        yield current.strftime('%Y-%m-%d')
        current += timedelta(days=1)


def is_rebalance_day(date_value: str, frequency: str, previous_rebalance: Optional[str]) -> bool:
    if previous_rebalance is None:
        return True
    d = parse_date(date_value)
    p = parse_date(previous_rebalance)
    if frequency == 'daily':
        return True
    if frequency == 'weekly':
        return d.isocalendar().week != p.isocalendar().week or d.year != p.year
    if frequency == 'monthly':
        return d.month != p.month or d.year != p.year
    return False


class BacktestEngine:
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
        rebalance: str = 'monthly',
        min_score: Optional[float] = None,
        tickers: Optional[Sequence[str]] = None,
        transaction_cost: float = 0.001,
        dry_run: bool = False,
        limit: Optional[int] = None,
        mode: str = 'no_lookahead',
    ) -> Dict:
        if strategy != 'score_top_n':
            raise ValueError('Estratégia suportada neste engine base: score_top_n')
        if mode not in VALID_MODES:
            raise ValueError("mode inválido. Use 'no_lookahead' ou 'research'.")

        diagnostics = BacktestDiagnostics(enabled=True)
        if mode == 'research':
            diagnostics.warning('MODO RESEARCH: usa scores atuais sobre histórico. Não é backtest sem viés.')

        effective_top_n = max(1, min(int(top_n), int(limit))) if limit else max(1, int(top_n))
        repo = self.repository
        portfolio = PortfolioManager(initial_capital, transaction_cost=transaction_cost)
        diagnostics.info('Portfolio inicializado', initial_capital=initial_capital, cash=portfolio.cash, transaction_cost=transaction_cost)
        risk = RiskManager(max_position_pct=1 / max(1, effective_top_n))
        selector = StrategyScoreTopN(repo, top_n=effective_top_n, asset_class=asset_class, min_score=min_score, tickers=tickers, mode=mode)

        backtest_id = 0
        params = {
            'strategy': strategy,
            'asset_class': asset_class,
            'top_n': effective_top_n,
            'rebalance_frequency': rebalance,
            'transaction_cost': transaction_cost,
            'min_score': min_score,
            'mode': mode,
            'limit': limit,
        }
        if not dry_run:
            backtest_id = repo.create_run(
                strategy_name=strategy,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                **params,
            )

        equity_curve: List[Dict] = []
        trades_to_persist: List[Dict] = []
        skipped_events: List[Dict] = []
        previous_rebalance: Optional[str] = None

        try:
            for current_date in date_range(start_date, end_date):
                if is_rebalance_day(current_date, rebalance, previous_rebalance):
                    selected = selector.select(current_date)
                    diag = getattr(selector, 'last_diagnostics', {}) or {}
                    previous_rebalance = current_date
                    selected_set = set(selected)
                    diagnostics.info(
                        'Rebalanceamento iniciado',
                        date=current_date,
                        mode=mode,
                        scores_found=diag.get('scores_found', 0),
                        rankings_found=diag.get('rankings_found', 0),
                        source_used=diag.get('source_used'),
                        scores_total_db=diag.get('scores_total_db'),
                        scores_after_filter=diag.get('scores_after_filter'),
                        score_filter_applied=diag.get('score_filter_applied'),
                        asset_class_filter_requested=diag.get('asset_class_filter_requested'),
                        asset_class_filter_effective=diag.get('asset_class_filter_effective'),
                        candidate_tickers=diag.get('candidate_tickers', []),
                        selected_tickers=selected,
                    )
                    if not selected:
                        reason = diag.get('reason') or 'Estratégia retornou lista vazia para os filtros informados.'
                        skipped_events.append({'date': current_date, 'ticker': None, 'reason': reason})
                        diagnostics.warning('Nenhum ativo selecionado', date=current_date, reason=reason)

                    orders_generated = 0
                    orders_executed = 0

                    # PATCH 9.5 — Rebalanceamento real:
                    # 1) calcula target por ativo;
                    # 2) executa TODAS as vendas primeiro;
                    # 3) executa compras depois usando o caixa atualizado.
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
                    diagnostics.info(
                        'Target allocation calculado',
                        date=current_date,
                        selected_count=selected_count,
                        equity=equity,
                        target_value_per_asset=target_value,
                        cash=portfolio.cash,
                    )

                    # Monta deltas de todos os ativos relevantes. Ativos fora do ranking têm alvo zero.
                    rebalance_plan: List[Dict] = []
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

                        rebalance_plan.append({
                            'ticker': ticker,
                            'exec_date': exec_date,
                            'price': price,
                            'current_value': current_value,
                            'target_value': target_for_ticker,
                            'delta': delta,
                            'action': action,
                            'quantity': quantity,
                        })
                        diagnostics.info(
                            'Delta de rebalanceamento calculado',
                            date=current_date,
                            ticker=ticker,
                            price=price,
                            current_value=current_value,
                            target_value=target_for_ticker,
                            delta=delta,
                            operation=action,
                            quantity=quantity,
                            cash=portfolio.cash,
                        )

                    # FASE 1: vendas primeiro.
                    for item in rebalance_plan:
                        if item['action'] != 'sell':
                            continue
                        orders_generated += 1
                        ticker = item['ticker']
                        cash_before = portfolio.cash
                        trade = portfolio.sell_quantity(
                            ticker=ticker,
                            price=item['price'],
                            quantity=item['quantity'],
                            date=item['exec_date'],
                            target_value=item['target_value'],
                            delta=item['delta'],
                        )
                        if trade:
                            orders_executed += 1
                            trades_to_persist.append(trade)
                            diagnostics.info(
                                'Ordem executada',
                                operation='sell',
                                ticker=ticker,
                                quantity=trade.get('quantity'),
                                price=trade.get('price'),
                                delta=item['delta'],
                                cash_before=cash_before,
                                cash_after=portfolio.cash,
                                target_value=item['target_value'],
                            )
                            if not dry_run:
                                repo.insert_trade(backtest_id, trade)
                        else:
                            reject = portfolio.last_reject_reason or {}
                            reason = reject.get('reason') or 'venda não executada'
                            skipped_events.append({'date': current_date, 'ticker': ticker, 'reason': reason})
                            diagnostics.warning(
                                'Ordem não executada',
                                operation='sell',
                                ticker=ticker,
                                quantity=item['quantity'],
                                price=item['price'],
                                delta=item['delta'],
                                cash_before=cash_before,
                                cash_after=portfolio.cash,
                                reason=reason,
                            )

                    # FASE 2: compras depois das vendas, com caixa atualizado.
                    for item in rebalance_plan:
                        if item['action'] != 'buy':
                            if item['action'].startswith('skip_'):
                                skipped_events.append({'date': current_date, 'ticker': item['ticker'], 'reason': item['action']})
                                diagnostics.info(
                                    'Ordem ignorada',
                                    operation=item['action'],
                                    ticker=item['ticker'],
                                    price=item['price'],
                                    delta=item['delta'],
                                    quantity=item['quantity'],
                                    cash=portfolio.cash,
                                )
                            continue

                        ticker = item['ticker']
                        # Recalcula delta após as vendas, pois o equity/cash mudou por taxa/custos.
                        current_value = portfolio.position_value(ticker, item['price'])
                        refreshed_delta = max(0.0, item['target_value'] - current_value)
                        if refreshed_delta <= 0:
                            diagnostics.info(
                                'Compra ignorada após vendas',
                                ticker=ticker,
                                current_value=current_value,
                                target_value=item['target_value'],
                                delta=refreshed_delta,
                                reason='posição já está no alvo ou acima do alvo',
                            )
                            continue

                        orders_generated += 1
                        preview = portfolio.preview_buy_to_value(ticker, item['price'], refreshed_delta)
                        diagnostics.info(
                            'Sizing de compra calculado',
                            date=current_date,
                            ticker=ticker,
                            price=item['price'],
                            target_value=refreshed_delta,
                            delta=refreshed_delta,
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
                        trade = portfolio.buy_to_value(ticker, item['price'], refreshed_delta, item['exec_date'])
                        if trade:
                            orders_executed += 1
                            trades_to_persist.append(trade)
                            trade['delta'] = refreshed_delta
                            diagnostics.info(
                                'Ordem executada',
                                operation='buy',
                                ticker=ticker,
                                quantity=trade.get('quantity'),
                                price=trade.get('price'),
                                delta=refreshed_delta,
                                buy_value=trade.get('gross_value'),
                                cash_before=cash_before,
                                cash_after=portfolio.cash,
                                target_value=item['target_value'],
                            )
                            if not dry_run:
                                repo.insert_trade(backtest_id, trade)
                        else:
                            reject = portfolio.last_reject_reason or preview
                            reason = reject.get('reason') or 'compra não executada'
                            skipped_events.append({'date': current_date, 'ticker': ticker, 'reason': reason})
                            diagnostics.warning(
                                'Ordem não executada',
                                operation='buy',
                                ticker=ticker,
                                quantity=reject.get('quantity'),
                                price=item['price'],
                                delta=refreshed_delta,
                                buy_value=reject.get('buy_value'),
                                total_cost=reject.get('total_cost'),
                                cash_before=reject.get('cash_before', cash_before),
                                cash_after=portfolio.cash,
                                reason=reason,
                            )

                    diagnostics.info('Rebalanceamento finalizado', date=current_date, orders_generated=orders_generated, orders_executed=orders_executed, cash=portfolio.cash)

                price_map = self._current_prices(list(portfolio.positions.keys()), current_date)
                positions_value = portfolio.positions_value(price_map)
                equity_value = portfolio.cash + positions_value
                curve_row = {'date': current_date, 'equity_value': equity_value, 'cash': portfolio.cash, 'positions_value': positions_value}
                equity_curve.append(curve_row)
                if not dry_run:
                    repo.insert_equity(backtest_id, current_date, equity_value, portfolio.cash, positions_value)
                    for ticker, pos in portfolio.positions.items():
                        repo.upsert_position(backtest_id, ticker, pos.quantity, pos.avg_price, price_map.get(ticker), current_date)

            metrics = calculate_backtest_metrics(equity_curve, trades_to_persist, initial_capital)
            metrics.update({'backtest_id': backtest_id, 'skipped_events': len(skipped_events), 'mode': mode})
            if not dry_run:
                repo.insert_metrics(backtest_id, metrics)
                repo.finish_run(backtest_id, 'success')
                repo.commit()
            diagnostics.info('Backtest finalizado', backtest_id=backtest_id, trades=len(trades_to_persist), skipped_events=len(skipped_events), metrics=metrics)
            return {
                'backtest_id': backtest_id,
                'metrics': metrics,
                'trades': len(trades_to_persist),
                'skipped_events': skipped_events[:50],
                'diagnostics': diagnostics.events[:200],
                'dry_run': dry_run,
                'mode': mode,
            }
        except Exception as exc:
            diagnostics.error('Backtest falhou', error=str(exc))
            if not dry_run and backtest_id:
                repo.finish_run(backtest_id, 'failed', str(exc))
            raise

    def _current_prices(self, tickers: Sequence[str], as_of_date: str) -> Dict[str, float]:
        prices: Dict[str, float] = {}
        for ticker in tickers:
            price = self.repository.get_close_on_or_before(ticker, as_of_date)
            if price is not None:
                prices[ticker] = price
        return prices
