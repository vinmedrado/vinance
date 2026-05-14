import json
from db import pg_compat as dbcompat
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parents[3] / 'data' / 'POSTGRES_RUNTIME_DISABLED'


def get_connection(db_path: Optional[str] = None) -> dbcompat.Connection:
    path = Path(db_path) if db_path else ROOT_DIR
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = dbcompat.connect(str(path))
    conn.row_factory = dbcompat.Row
    return conn


class BacktestRepository:
    def __init__(self, conn: Optional[dbcompat.Connection] = None, db_path: Optional[str] = None):
        self.conn = conn or get_connection(db_path)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS backtest_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            asset_class TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            initial_capital REAL NOT NULL,
            top_n INTEGER,
            rebalance_frequency TEXT,
            transaction_cost REAL DEFAULT 0.001,
            status TEXT DEFAULT 'created',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            params_json TEXT,
            error_message TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS backtest_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            action TEXT NOT NULL,
            date TEXT NOT NULL,
            price REAL NOT NULL,
            quantity REAL NOT NULL,
            gross_value REAL DEFAULT 0,
            transaction_cost REAL DEFAULT 0,
            net_value REAL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS backtest_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_price REAL NOT NULL,
            last_price REAL,
            market_value REAL,
            last_updated TEXT NOT NULL,
            UNIQUE(backtest_id, ticker)
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS backtest_equity_curve (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            equity_value REAL NOT NULL,
            cash REAL DEFAULT 0,
            positions_value REAL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(backtest_id, date)
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS backtest_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id INTEGER NOT NULL UNIQUE,
            total_return REAL,
            annual_return REAL,
            volatility REAL,
            max_drawdown REAL,
            sharpe_ratio REAL,
            win_rate REAL,
            total_trades INTEGER,
            turnover REAL,
            metrics_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('CREATE INDEX IF NOT EXISTS ix_backtest_trades_run ON backtest_trades(backtest_id, date)')
        cur.execute('CREATE INDEX IF NOT EXISTS ix_backtest_equity_run ON backtest_equity_curve(backtest_id, date)')
        self.conn.commit()

    def create_run(self, strategy_name: str, start_date: str, end_date: str, initial_capital: float, **params: Any) -> int:
        cur = self.conn.cursor()
        cur.execute('''INSERT INTO backtest_runs
            (strategy_name, asset_class, start_date, end_date, initial_capital, top_n, rebalance_frequency, transaction_cost, status, params_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)''',
            (strategy_name, params.get('asset_class'), start_date, end_date, initial_capital, params.get('top_n'),
             params.get('rebalance_frequency'), params.get('transaction_cost', 0.001), json.dumps(params, ensure_ascii=False)))
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, backtest_id: int, status: str = 'success', error_message: Optional[str] = None) -> None:
        self.conn.execute('UPDATE backtest_runs SET status=?, finished_at=CURRENT_TIMESTAMP, error_message=? WHERE id=?', (status, error_message, backtest_id))
        self.conn.commit()

    def list_assets(self, asset_class: str = 'all', limit: Optional[int] = None) -> List[dbcompat.Row]:
        sql = 'SELECT id, ticker, name, asset_class FROM assets WHERE 1=1'
        params: List[Any] = []
        if asset_class and asset_class != 'all':
            sql += ' AND asset_class = ?'
            params.append(asset_class)
        sql += ' ORDER BY ticker'
        if limit:
            sql += ' LIMIT ?'
            params.append(limit)
        return list(self.conn.execute(sql, params))

    def get_scores_for_date(self, as_of_date: str, asset_class: str = 'all', top_n: int = 10, min_score: Optional[float] = None, tickers: Optional[Sequence[str]] = None) -> List[dbcompat.Row]:
        filters = ['date(calculated_at) <= date(?)', 'score_total IS NOT NULL']
        params: List[Any] = [as_of_date]
        if asset_class and asset_class != 'all':
            filters.append('asset_class = ?')
            params.append(asset_class)
        if min_score is not None:
            filters.append('score_total >= ?')
            params.append(min_score)
        if tickers:
            placeholders = ','.join(['?'] * len(tickers))
            filters.append(f'ticker IN ({placeholders})')
            params.extend([t.strip().upper() for t in tickers])
        sql = f'''
            SELECT s.* FROM asset_scores s
            INNER JOIN (
                SELECT ticker, MAX(calculated_at) AS max_calc
                FROM asset_scores
                WHERE {' AND '.join(filters)}
                GROUP BY ticker
            ) latest ON latest.ticker = s.ticker AND latest.max_calc = s.calculated_at
            ORDER BY s.score_total DESC
            LIMIT ?
        '''
        params.append(top_n)
        return list(self.conn.execute(sql, params))

    def get_next_close(self, ticker: str, after_date: str) -> Optional[dbcompat.Row]:
        return self.conn.execute('''
            SELECT p.date, p.close
            FROM asset_prices p
            JOIN assets a ON a.id = p.asset_id
            WHERE a.ticker = ? AND date(p.date) > date(?) AND p.close IS NOT NULL AND p.close > 0
            ORDER BY date(p.date) ASC
            LIMIT 1
        ''', (ticker, after_date)).fetchone()

    def get_close_on_or_before(self, ticker: str, as_of_date: str) -> Optional[float]:
        row = self.conn.execute('''
            SELECT p.close FROM asset_prices p
            JOIN assets a ON a.id = p.asset_id
            WHERE a.ticker = ? AND date(p.date) <= date(?) AND p.close IS NOT NULL AND p.close > 0
            ORDER BY date(p.date) DESC LIMIT 1
        ''', (ticker, as_of_date)).fetchone()
        return float(row['close']) if row else None

    def insert_trade(self, backtest_id: int, trade: Dict[str, Any]) -> None:
        self.conn.execute('''INSERT INTO backtest_trades
            (backtest_id, ticker, action, date, price, quantity, gross_value, transaction_cost, net_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (backtest_id, trade['ticker'], trade['action'], trade['date'], trade['price'], trade['quantity'],
             trade.get('gross_value', 0), trade.get('transaction_cost', 0), trade.get('net_value', 0)))

    def upsert_position(self, backtest_id: int, ticker: str, quantity: float, avg_price: float, last_price: Optional[float], date_value: str) -> None:
        market_value = (last_price or avg_price) * quantity
        self.conn.execute('''INSERT INTO backtest_positions
            (backtest_id, ticker, quantity, avg_price, last_price, market_value, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(backtest_id, ticker) DO UPDATE SET
                quantity=excluded.quantity, avg_price=excluded.avg_price, last_price=excluded.last_price,
                market_value=excluded.market_value, last_updated=excluded.last_updated''',
            (backtest_id, ticker, quantity, avg_price, last_price, market_value, date_value))

    def insert_equity(self, backtest_id: int, date_value: str, equity: float, cash: float, positions_value: float) -> None:
        self.conn.execute('''INSERT INTO backtest_equity_curve(backtest_id, date, equity_value, cash, positions_value)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(backtest_id, date) DO UPDATE SET equity_value=excluded.equity_value, cash=excluded.cash, positions_value=excluded.positions_value''',
            (backtest_id, date_value, equity, cash, positions_value))

    def insert_metrics(self, backtest_id: int, metrics: Dict[str, Any]) -> None:
        self.conn.execute('''INSERT INTO backtest_metrics
            (backtest_id, total_return, annual_return, volatility, max_drawdown, sharpe_ratio, win_rate, total_trades, turnover, metrics_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(backtest_id) DO UPDATE SET
                total_return=excluded.total_return, annual_return=excluded.annual_return, volatility=excluded.volatility,
                max_drawdown=excluded.max_drawdown, sharpe_ratio=excluded.sharpe_ratio, win_rate=excluded.win_rate,
                total_trades=excluded.total_trades, turnover=excluded.turnover, metrics_json=excluded.metrics_json''',
            (backtest_id, metrics.get('total_return'), metrics.get('annual_return'), metrics.get('volatility'),
             metrics.get('max_drawdown'), metrics.get('sharpe_ratio'), metrics.get('win_rate'), metrics.get('total_trades'),
             metrics.get('turnover'), json.dumps(metrics, ensure_ascii=False)))

    def commit(self) -> None:
        self.conn.commit()

    def latest_runs(self, limit: int = 5) -> List[dbcompat.Row]:
        return list(self.conn.execute('SELECT * FROM backtest_runs ORDER BY id DESC LIMIT ?', (limit,)))


# PATCH 10 extensions -------------------------------------------------------
def _bt_get_strategy_universe(self, as_of_date, asset_class='all', tickers=None):
    """Retorna universo com último score e últimas métricas disponíveis até a data.

    Mantém a regra anti-lookahead: apenas registros com calculated_at/as_of_date <= as_of_date.
    """
    import json as _json
    outer_filters = ['date(s.calculated_at) <= date(?)']
    inner_filters = ['date(calculated_at) <= date(?)']
    outer_params = [as_of_date]
    inner_params = [as_of_date]
    if asset_class and asset_class != 'all':
        outer_filters.append('s.asset_class = ?')
        inner_filters.append('asset_class = ?')
        outer_params.append(asset_class)
        inner_params.append(asset_class)
    if tickers:
        placeholders = ','.join(['?'] * len(tickers))
        clean_tickers = [str(t).strip().upper() for t in tickers]
        outer_filters.append(f's.ticker IN ({placeholders})')
        inner_filters.append(f'ticker IN ({placeholders})')
        outer_params.extend(clean_tickers)
        inner_params.extend(clean_tickers)
    outer_where = ' AND '.join(outer_filters)
    inner_where = ' AND '.join(inner_filters)
    sql = f'''
        SELECT s.*, m.metrics_json
        FROM asset_scores s
        LEFT JOIN asset_analysis_metrics m
          ON m.ticker = s.ticker
         AND date(m.as_of_date) <= date(?)
         AND m.as_of_date = (
             SELECT MAX(m2.as_of_date)
             FROM asset_analysis_metrics m2
             WHERE m2.ticker = s.ticker AND date(m2.as_of_date) <= date(?)
         )
        INNER JOIN (
            SELECT ticker, MAX(calculated_at) AS max_calc
            FROM asset_scores
            WHERE {inner_where}
            GROUP BY ticker
        ) latest ON latest.ticker = s.ticker AND latest.max_calc = s.calculated_at
        WHERE {outer_where}
    '''
    query_params = [as_of_date, as_of_date] + inner_params + outer_params
    rows = []
    for row in self.conn.execute(sql, query_params):
        item = dict(row)
        raw = item.pop('metrics_json', None)
        try:
            item['metrics'] = _json.loads(raw) if raw else {}
        except Exception:
            item['metrics'] = {}
        rows.append(item)
    return rows


BacktestRepository.get_strategy_universe = _bt_get_strategy_universe

# PATCH 9.1 HOTFIX - diagnostic/research selection helpers ------------------
def _bt_table_exists(self, table_name: str) -> bool:
    row = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    return row is not None


def _bt_normalize_tickers(tickers):
    if not tickers:
        return None
    cleaned = [str(t).strip().upper() for t in tickers if str(t).strip()]
    return cleaned or None


def _bt_count_scores(self, as_of_date, asset_class='all', tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_scores'):
        return 0
    filters = ['score_total IS NOT NULL']
    params = []
    if mode != 'research':
        filters.append('date(calculated_at) <= date(?)')
        params.append(as_of_date)
    if asset_class and asset_class != 'all':
        filters.append('asset_class = ?')
        params.append(asset_class)
    clean = _bt_normalize_tickers(tickers)
    if clean:
        filters.append('ticker IN (%s)' % ','.join(['?'] * len(clean)))
        params.extend(clean)
    sql = 'SELECT COUNT(*) AS total FROM asset_scores WHERE ' + ' AND '.join(filters)
    row = self.conn.execute(sql, params).fetchone()
    return int(row['total'] if row else 0)


def _bt_count_rankings(self, as_of_date, asset_class='all', tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_rankings'):
        return 0
    filters = ["ranking_type = 'score_total'", 'score_value IS NOT NULL']
    params = []
    if mode != 'research':
        filters.append('date(calculated_at) <= date(?)')
        params.append(as_of_date)
    if asset_class and asset_class != 'all':
        filters.append('asset_class = ?')
        params.append(asset_class)
    clean = _bt_normalize_tickers(tickers)
    if clean:
        filters.append('ticker IN (%s)' % ','.join(['?'] * len(clean)))
        params.extend(clean)
    sql = 'SELECT COUNT(*) AS total FROM asset_rankings WHERE ' + ' AND '.join(filters)
    row = self.conn.execute(sql, params).fetchone()
    return int(row['total'] if row else 0)


def _bt_latest_rankings(self, as_of_date, asset_class='all', top_n=10, min_score=None, tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_rankings'):
        return []
    filters = ["r.ranking_type = 'score_total'", 'r.score_value IS NOT NULL']
    params = []
    inner_filters = ["ranking_type = 'score_total'", 'score_value IS NOT NULL']
    inner_params = []
    if mode != 'research':
        filters.append('date(r.calculated_at) <= date(?)')
        params.append(as_of_date)
        inner_filters.append('date(calculated_at) <= date(?)')
        inner_params.append(as_of_date)
    if asset_class and asset_class != 'all':
        filters.append('r.asset_class = ?')
        params.append(asset_class)
        inner_filters.append('asset_class = ?')
        inner_params.append(asset_class)
    if min_score is not None:
        filters.append('r.score_value >= ?')
        params.append(float(min_score))
        inner_filters.append('score_value >= ?')
        inner_params.append(float(min_score))
    clean = _bt_normalize_tickers(tickers)
    if clean:
        ph = ','.join(['?'] * len(clean))
        filters.append(f'r.ticker IN ({ph})')
        params.extend(clean)
        inner_filters.append(f'ticker IN ({ph})')
        inner_params.extend(clean)
    # Usa a última data de ranking disponível; em research ignora a data simulada.
    inner_where = ' AND '.join(inner_filters)
    where = ' AND '.join(filters)
    sql = f'''
        SELECT r.asset_id, r.ticker, r.asset_class, r.score_value AS score_total, r.calculated_at,
               r.rank_position, 'asset_rankings' AS source_table
        FROM asset_rankings r
        WHERE {where}
          AND r.calculated_at = (SELECT MAX(calculated_at) FROM asset_rankings WHERE {inner_where})
        ORDER BY r.rank_position ASC, r.score_value DESC
        LIMIT ?
    '''
    return [dict(x) for x in self.conn.execute(sql, params + inner_params + [int(top_n)])]


def _bt_latest_scores(self, as_of_date, asset_class='all', top_n=10, min_score=None, tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_scores'):
        return []
    filters = ['s.score_total IS NOT NULL']
    latest_filters = ['score_total IS NOT NULL']
    params = []
    latest_params = []
    if mode != 'research':
        filters.append('date(s.calculated_at) <= date(?)')
        params.append(as_of_date)
        latest_filters.append('date(calculated_at) <= date(?)')
        latest_params.append(as_of_date)
    if asset_class and asset_class != 'all':
        filters.append('s.asset_class = ?')
        params.append(asset_class)
        latest_filters.append('asset_class = ?')
        latest_params.append(asset_class)
    if min_score is not None:
        filters.append('s.score_total >= ?')
        params.append(float(min_score))
        latest_filters.append('score_total >= ?')
        latest_params.append(float(min_score))
    clean = _bt_normalize_tickers(tickers)
    if clean:
        ph = ','.join(['?'] * len(clean))
        filters.append(f's.ticker IN ({ph})')
        params.extend(clean)
        latest_filters.append(f'ticker IN ({ph})')
        latest_params.extend(clean)
    where = ' AND '.join(filters)
    latest_where = ' AND '.join(latest_filters)
    sql = f'''
        SELECT s.*, 'asset_scores' AS source_table
        FROM asset_scores s
        INNER JOIN (
            SELECT ticker, MAX(calculated_at) AS max_calc
            FROM asset_scores
            WHERE {latest_where}
            GROUP BY ticker
        ) latest ON latest.ticker = s.ticker AND latest.max_calc = s.calculated_at
        WHERE {where}
        ORDER BY s.score_total DESC
        LIMIT ?
    '''
    return [dict(x) for x in self.conn.execute(sql, latest_params + params + [int(top_n)])]


def _bt_select_score_top_n(self, as_of_date, asset_class='all', top_n=10, min_score=None, tickers=None, mode='no_lookahead'):
    rankings_count = _bt_count_rankings(self, as_of_date, asset_class, tickers, mode)
    scores_count = _bt_count_scores(self, as_of_date, asset_class, tickers, mode)
    rows = _bt_latest_rankings(self, as_of_date, asset_class, top_n, min_score, tickers, mode)
    source = 'asset_rankings'
    if not rows:
        rows = _bt_latest_scores(self, as_of_date, asset_class, top_n, min_score, tickers, mode)
        source = 'asset_scores'
    diagnostics = {
        'mode': mode,
        'date': as_of_date,
        'asset_class': asset_class,
        'rankings_found': rankings_count,
        'scores_found': scores_count,
        'source_used': source if rows else None,
        'candidate_tickers': [str(r.get('ticker')) for r in rows],
        'selected_tickers': [str(r.get('ticker')) for r in rows[:int(top_n)]],
        'reason': None,
    }
    if not rows:
        if mode == 'no_lookahead':
            diagnostics['reason'] = 'Nenhum ranking/score com calculated_at <= data simulada. Rode em --mode=research para validar execução com scores atuais, ou gere histórico de scores.'
        else:
            diagnostics['reason'] = 'Nenhum ranking/score atual encontrado para os filtros informados.'
    return rows[:int(top_n)], diagnostics


def _bt_get_strategy_universe_hotfix(self, as_of_date, asset_class='all', tickers=None, mode='no_lookahead'):
    import json as _json
    rows = _bt_latest_scores(self, as_of_date, asset_class, 1000000, None, tickers, mode)
    out = []
    for item in rows:
        ticker = item.get('ticker')
        metric_filter = 'm.ticker = ?'
        metric_params = [ticker]
        if mode != 'research':
            metric_filter += ' AND date(m.as_of_date) <= date(?)'
            metric_params.append(as_of_date)
        metric_sql = f'''
            SELECT m.metrics_json
            FROM asset_analysis_metrics m
            WHERE {metric_filter}
            ORDER BY date(m.as_of_date) DESC, date(m.calculated_at) DESC
            LIMIT 1
        '''
        mrow = self.conn.execute(metric_sql, metric_params).fetchone() if _bt_table_exists(self, 'asset_analysis_metrics') else None
        raw = mrow['metrics_json'] if mrow else None
        try:
            item['metrics'] = _json.loads(raw) if raw else {}
        except Exception:
            item['metrics'] = {}
        out.append(item)
    return out


BacktestRepository.table_exists = _bt_table_exists
BacktestRepository.count_scores = _bt_count_scores
BacktestRepository.count_rankings = _bt_count_rankings
BacktestRepository.select_score_top_n = _bt_select_score_top_n
BacktestRepository.get_strategy_universe = _bt_get_strategy_universe_hotfix

# PATCH 9.2 HOTFIX - Corrige modo research para ignorar filtro temporal de verdade
# Mantém no_lookahead intacto: quando mode != 'research', calculated_at <= as_of_date continua obrigatório.
def _bt92_norm_mode(mode):
    return 'research' if str(mode or '').lower() == 'research' else 'no_lookahead'


def _bt92_normalize_tickers(tickers):
    if not tickers:
        return None
    cleaned = [str(t).strip().upper() for t in tickers if str(t).strip()]
    return cleaned or None


def _bt92_rankings_base_where(as_of_date, asset_class='all', min_score=None, tickers=None, mode='no_lookahead'):
    mode = _bt92_norm_mode(mode)
    filters = ["r.ranking_type = 'score_total'", 'r.score_value IS NOT NULL']
    params = []
    # CRÍTICO: research NÃO aplica filtro temporal.
    if mode != 'research':
        filters.append('date(r.calculated_at) <= date(?)')
        params.append(as_of_date)
    if asset_class and asset_class != 'all':
        filters.append("LOWER(COALESCE(NULLIF(r.asset_class,''), NULLIF(a.asset_class,''))) = LOWER(?)")
        params.append(asset_class)
    if min_score is not None:
        filters.append('r.score_value >= ?')
        params.append(float(min_score))
    clean = _bt92_normalize_tickers(tickers)
    if clean:
        ph = ','.join(['?'] * len(clean))
        filters.append(f"UPPER(COALESCE(NULLIF(r.ticker,''), NULLIF(a.ticker,''))) IN ({ph})")
        params.extend(clean)
    return ' AND '.join(filters), params


def _bt92_scores_base_where(as_of_date, asset_class='all', min_score=None, tickers=None, mode='no_lookahead'):
    mode = _bt92_norm_mode(mode)
    filters = ['s.score_total IS NOT NULL']
    params = []
    # CRÍTICO: research NÃO aplica filtro temporal.
    if mode != 'research':
        filters.append('date(s.calculated_at) <= date(?)')
        params.append(as_of_date)
    if asset_class and asset_class != 'all':
        filters.append("LOWER(COALESCE(NULLIF(s.asset_class,''), NULLIF(a.asset_class,''))) = LOWER(?)")
        params.append(asset_class)
    if min_score is not None:
        filters.append('s.score_total >= ?')
        params.append(float(min_score))
    clean = _bt92_normalize_tickers(tickers)
    if clean:
        ph = ','.join(['?'] * len(clean))
        filters.append(f"UPPER(COALESCE(NULLIF(s.ticker,''), NULLIF(a.ticker,''))) IN ({ph})")
        params.extend(clean)
    return ' AND '.join(filters), params


def _bt92_count_scores(self, as_of_date, asset_class='all', tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_scores'):
        return 0
    where, params = _bt92_scores_base_where(as_of_date, asset_class, None, tickers, mode)
    sql = f'''
        SELECT COUNT(*) AS total
        FROM asset_scores s
        LEFT JOIN assets a ON a.id = s.asset_id
        WHERE {where}
    '''
    row = self.conn.execute(sql, params).fetchone()
    return int(row['total'] if row else 0)


def _bt92_count_rankings(self, as_of_date, asset_class='all', tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_rankings'):
        return 0
    where, params = _bt92_rankings_base_where(as_of_date, asset_class, None, tickers, mode)
    sql = f'''
        SELECT COUNT(*) AS total
        FROM asset_rankings r
        LEFT JOIN assets a ON a.id = r.asset_id
        WHERE {where}
    '''
    row = self.conn.execute(sql, params).fetchone()
    return int(row['total'] if row else 0)


def _bt92_latest_scores(self, as_of_date, asset_class='all', top_n=10, min_score=None, tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_scores'):
        return []
    mode = _bt92_norm_mode(mode)
    where, params = _bt92_scores_base_where(as_of_date, asset_class, min_score, tickers, mode)
    # Usa o último snapshot por ativo/ticker. Em research, isso é independente da data simulada.
    sql = f'''
        SELECT * FROM (
            SELECT
                COALESCE(s.asset_id, a.id) AS asset_id,
                UPPER(COALESCE(NULLIF(s.ticker,''), NULLIF(a.ticker,''))) AS ticker,
                COALESCE(NULLIF(s.asset_class,''), NULLIF(a.asset_class,'')) AS asset_class,
                s.score_total,
                s.score_retorno,
                s.score_risco,
                s.score_liquidez,
                s.score_dividendos,
                s.score_tendencia,
                s.explanation,
                s.calculated_at,
                'asset_scores' AS source_table,
                ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(s.asset_id, a.id, UPPER(COALESCE(NULLIF(s.ticker,''), NULLIF(a.ticker,''))))
                    ORDER BY datetime(s.calculated_at) DESC, s.id DESC
                ) AS rn
            FROM asset_scores s
            LEFT JOIN assets a ON a.id = s.asset_id
            WHERE {where}
        ) latest
        WHERE rn = 1
        ORDER BY score_total DESC
        LIMIT ?
    '''
    return [dict(x) for x in self.conn.execute(sql, params + [int(top_n)])]


def _bt92_latest_rankings(self, as_of_date, asset_class='all', top_n=10, min_score=None, tickers=None, mode='no_lookahead'):
    if not _bt_table_exists(self, 'asset_rankings'):
        return []
    mode = _bt92_norm_mode(mode)
    where, params = _bt92_rankings_base_where(as_of_date, asset_class, min_score, tickers, mode)
    # Usa o último snapshot de ranking por ativo/ticker. Em research, sem filtro de data simulada.
    sql = f'''
        SELECT * FROM (
            SELECT
                COALESCE(r.asset_id, a.id) AS asset_id,
                UPPER(COALESCE(NULLIF(r.ticker,''), NULLIF(a.ticker,''))) AS ticker,
                COALESCE(NULLIF(r.asset_class,''), NULLIF(a.asset_class,'')) AS asset_class,
                r.score_value AS score_total,
                r.calculated_at,
                r.rank_position,
                'asset_rankings' AS source_table,
                ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(r.asset_id, a.id, UPPER(COALESCE(NULLIF(r.ticker,''), NULLIF(a.ticker,''))))
                    ORDER BY datetime(r.calculated_at) DESC, r.rank_position ASC, r.id DESC
                ) AS rn
            FROM asset_rankings r
            LEFT JOIN assets a ON a.id = r.asset_id
            WHERE {where}
        ) latest
        WHERE rn = 1
        ORDER BY rank_position ASC, score_total DESC
        LIMIT ?
    '''
    return [dict(x) for x in self.conn.execute(sql, params + [int(top_n)])]


def _bt92_select_score_top_n(self, as_of_date, asset_class='all', top_n=10, min_score=None, tickers=None, mode='no_lookahead'):
    mode = _bt92_norm_mode(mode)
    rankings_count = _bt92_count_rankings(self, as_of_date, asset_class, tickers, mode)
    scores_count = _bt92_count_scores(self, as_of_date, asset_class, tickers, mode)
    rows = _bt92_latest_rankings(self, as_of_date, asset_class, top_n, min_score, tickers, mode)
    source = 'asset_rankings'
    if not rows:
        rows = _bt92_latest_scores(self, as_of_date, asset_class, top_n, min_score, tickers, mode)
        source = 'asset_scores'
    diagnostics = {
        'mode': mode,
        'date': as_of_date,
        'asset_class': asset_class,
        'temporal_filter_applied': mode != 'research',
        'rankings_found': rankings_count,
        'scores_found': scores_count,
        'source_used': source if rows else None,
        'candidate_tickers': [str(r.get('ticker')) for r in rows],
        'selected_tickers': [str(r.get('ticker')) for r in rows[:int(top_n)]],
        'reason': None,
    }
    if not rows:
        if mode == 'no_lookahead':
            diagnostics['reason'] = 'Nenhum ranking/score com calculated_at <= data simulada. Esse é o comportamento correto do modo no_lookahead. Use --mode=research para validar execução com scores atuais.'
        else:
            diagnostics['reason'] = 'Modo research ativo, mas nenhum score/ranking atual foi encontrado para os filtros. Rode a Analysis Engine antes ou revise asset_class/tickers.'
    return rows[:int(top_n)], diagnostics


def _bt92_get_strategy_universe(self, as_of_date, asset_class='all', tickers=None, mode='no_lookahead'):
    import json as _json
    rows = _bt92_latest_scores(self, as_of_date, asset_class, 1000000, None, tickers, mode)
    out = []
    for item in rows:
        ticker = item.get('ticker')
        metric_filter = 'UPPER(m.ticker) = UPPER(?)'
        metric_params = [ticker]
        if _bt92_norm_mode(mode) != 'research':
            metric_filter += ' AND date(m.as_of_date) <= date(?)'
            metric_params.append(as_of_date)
        metric_sql = f'''
            SELECT m.metrics_json
            FROM asset_analysis_metrics m
            WHERE {metric_filter}
            ORDER BY datetime(m.as_of_date) DESC, datetime(m.calculated_at) DESC
            LIMIT 1
        '''
        mrow = self.conn.execute(metric_sql, metric_params).fetchone() if _bt_table_exists(self, 'asset_analysis_metrics') else None
        raw = mrow['metrics_json'] if mrow else None
        try:
            item['metrics'] = _json.loads(raw) if raw else {}
        except Exception:
            item['metrics'] = {}
        out.append(item)
    return out


# Reaplica os métodos no final do arquivo para sobrescrever o HOTFIX 9.1.
BacktestRepository.count_scores = _bt92_count_scores
BacktestRepository.count_rankings = _bt92_count_rankings
BacktestRepository.select_score_top_n = _bt92_select_score_top_n
BacktestRepository.get_strategy_universe = _bt92_get_strategy_universe

# PATCH 9.3 HOTFIX - Correção definitiva do modo research --------------------
# Objetivo: em mode='research', ignorar 100% o filtro temporal e recuperar
# scores atuais do banco mesmo quando asset_class estiver inconsistente.
# Importante: modo no_lookahead permanece delegado ao comportamento 9.2.
_BT92_SELECT_SCORE_TOP_N = BacktestRepository.select_score_top_n
_BT92_GET_STRATEGY_UNIVERSE = BacktestRepository.get_strategy_universe


def _bt93_mode(mode):
    return 'research' if str(mode or '').strip().lower() == 'research' else 'no_lookahead'


def _bt93_clean_tickers(tickers):
    if not tickers:
        return None
    cleaned = [str(t).strip().upper() for t in tickers if str(t).strip()]
    return cleaned or None


def _bt93_scalar(self, sql, params=None, default=0):
    try:
        row = self.conn.execute(sql, params or []).fetchone()
        if row is None:
            return default
        try:
            return row[0]
        except Exception:
            return row[list(row.keys())[0]]
    except Exception:
        return default


def _bt93_select_research_scores(self, asset_class='all', top_n=10, min_score=None, tickers=None):
    """Busca scores atuais SEM filtro temporal.

    Regra prática do hotfix:
    1. Conta todos os scores no banco.
    2. Tenta filtrar asset_class com LOWER/COALESCE.
    3. Se o filtro por classe zerar, remove asset_class automaticamente.
    4. Usa último snapshot por ativo/ticker.
    """
    if not _bt_table_exists(self, 'asset_scores'):
        return [], {
            'scores_total_db': 0,
            'scores_after_filter': 0,
            'score_filter_applied': 'asset_scores table missing',
            'asset_class_filter_requested': asset_class,
            'asset_class_filter_effective': None,
        }

    scores_total_db = int(_bt93_scalar(self, 'SELECT COUNT(*) FROM asset_scores', default=0) or 0)
    requested_class = None if not asset_class or asset_class == 'all' else str(asset_class).strip()
    clean = _bt93_clean_tickers(tickers)

    def build_where(use_asset_class=True):
        filters = ['s.score_total IS NOT NULL']
        params = []
        if use_asset_class and requested_class:
            filters.append("LOWER(COALESCE(NULLIF(s.asset_class,''), NULLIF(a.asset_class,''))) = LOWER(?)")
            params.append(requested_class)
        if min_score is not None:
            filters.append('s.score_total >= ?')
            params.append(float(min_score))
        if clean:
            ph = ','.join(['?'] * len(clean))
            filters.append(f"UPPER(COALESCE(NULLIF(s.ticker,''), NULLIF(a.ticker,''))) IN ({ph})")
            params.extend(clean)
        return ' AND '.join(filters), params

    # Primeira tentativa: com asset_class, case-insensitive.
    use_class = bool(requested_class)
    where, params = build_where(use_asset_class=use_class)
    count_sql = f'''
        SELECT COUNT(*)
        FROM asset_scores s
        LEFT JOIN assets a ON a.id = s.asset_id
        WHERE {where}
    '''
    scores_after_filter = int(_bt93_scalar(self, count_sql, params, default=0) or 0)
    effective_class = requested_class if use_class else None

    # Fallback obrigatório: se asset_class causar zero, remove o filtro.
    if requested_class and scores_after_filter == 0:
        use_class = False
        effective_class = None
        where, params = build_where(use_asset_class=False)
        count_sql = f'''
            SELECT COUNT(*)
            FROM asset_scores s
            LEFT JOIN assets a ON a.id = s.asset_id
            WHERE {where}
        '''
        scores_after_filter = int(_bt93_scalar(self, count_sql, params, default=0) or 0)

    sql = f'''
        SELECT * FROM (
            SELECT
                COALESCE(s.asset_id, a.id) AS asset_id,
                UPPER(COALESCE(NULLIF(s.ticker,''), NULLIF(a.ticker,''))) AS ticker,
                COALESCE(NULLIF(s.asset_class,''), NULLIF(a.asset_class,''), ?) AS asset_class,
                s.score_total,
                s.score_retorno,
                s.score_risco,
                s.score_liquidez,
                s.score_dividendos,
                s.score_tendencia,
                s.explanation,
                s.calculated_at,
                'asset_scores' AS source_table,
                ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(s.asset_id, a.id, UPPER(COALESCE(NULLIF(s.ticker,''), NULLIF(a.ticker,''))))
                    ORDER BY datetime(s.calculated_at) DESC
                ) AS rn
            FROM asset_scores s
            LEFT JOIN assets a ON a.id = s.asset_id
            WHERE {where}
        ) latest
        WHERE rn = 1
          AND ticker IS NOT NULL
          AND score_total IS NOT NULL
        ORDER BY score_total DESC
        LIMIT ?
    '''
    rows = [dict(x) for x in self.conn.execute(sql, [requested_class or effective_class or asset_class or 'unknown'] + params + [int(top_n)])]
    debug = {
        'scores_total_db': scores_total_db,
        'scores_after_filter': scores_after_filter,
        'score_filter_applied': where,
        'asset_class_filter_requested': requested_class,
        'asset_class_filter_effective': effective_class,
    }
    return rows, debug


def _bt93_select_score_top_n(self, as_of_date, asset_class='all', top_n=10, min_score=None, tickers=None, mode='no_lookahead'):
    mode = _bt93_mode(mode)
    if mode != 'research':
        # NÃO altera o modo seguro.
        return _BT92_SELECT_SCORE_TOP_N(self, as_of_date, asset_class, top_n, min_score, tickers, mode)

    rankings_count = 0
    if _bt_table_exists(self, 'asset_rankings'):
        # Apenas diagnóstico: não bloqueia fallback para scores.
        rankings_count = int(_bt93_scalar(self, 'SELECT COUNT(*) FROM asset_rankings', default=0) or 0)

    rows, debug = _bt93_select_research_scores(
        self,
        asset_class=asset_class,
        top_n=top_n,
        min_score=min_score,
        tickers=tickers,
    )

    diagnostics = {
        'mode': mode,
        'date': as_of_date,
        'asset_class': asset_class,
        'temporal_filter_applied': False,
        'rankings_found': rankings_count,
        'scores_found': int(debug.get('scores_after_filter', 0) or 0),
        'scores_total_db': int(debug.get('scores_total_db', 0) or 0),
        'scores_after_filter': int(debug.get('scores_after_filter', 0) or 0),
        'score_filter_applied': debug.get('score_filter_applied'),
        'asset_class_filter_requested': debug.get('asset_class_filter_requested'),
        'asset_class_filter_effective': debug.get('asset_class_filter_effective'),
        'source_used': 'scores' if rows else None,
        'candidate_tickers': [str(r.get('ticker')) for r in rows],
        'selected_tickers': [str(r.get('ticker')) for r in rows[:int(top_n)]],
        'reason': None,
    }
    if not rows:
        diagnostics['reason'] = (
            'Modo research ativo, mas asset_scores não retornou linhas. '
            f"scores_total_db={diagnostics['scores_total_db']}; "
            f"scores_after_filter={diagnostics['scores_after_filter']}; "
            f"filtro={diagnostics['score_filter_applied']}"
        )
    return rows[:int(top_n)], diagnostics


def _bt93_get_strategy_universe(self, as_of_date, asset_class='all', tickers=None, mode='no_lookahead'):
    mode = _bt93_mode(mode)
    if mode != 'research':
        return _BT92_GET_STRATEGY_UNIVERSE(self, as_of_date, asset_class, tickers, mode)
    import json as _json
    rows, _debug = _bt93_select_research_scores(self, asset_class=asset_class, top_n=1000000, min_score=None, tickers=tickers)
    out = []
    for item in rows:
        ticker = item.get('ticker')
        mrow = None
        if ticker and _bt_table_exists(self, 'asset_analysis_metrics'):
            mrow = self.conn.execute('''
                SELECT m.metrics_json
                FROM asset_analysis_metrics m
                WHERE UPPER(m.ticker) = UPPER(?)
                ORDER BY datetime(m.as_of_date) DESC, datetime(m.calculated_at) DESC
                LIMIT 1
            ''', (ticker,)).fetchone()
        raw = mrow['metrics_json'] if mrow else None
        try:
            item['metrics'] = _json.loads(raw) if raw else {}
        except Exception:
            item['metrics'] = {}
        out.append(item)
    return out


BacktestRepository.select_score_top_n = _bt93_select_score_top_n
BacktestRepository.get_strategy_universe = _bt93_get_strategy_universe
