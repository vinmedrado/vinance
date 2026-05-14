import json
from db import pg_compat as dbcompat
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[4] / 'data' / 'POSTGRES_RUNTIME_DISABLED'


class OptimizationRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.conn = dbcompat.connect(str(Path(db_path) if db_path else ROOT_DIR))
        self.conn.row_factory = dbcompat.Row
        self.ensure_schema()

    def ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS optimization_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            asset_class TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            mode TEXT DEFAULT 'grid_search',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            status TEXT DEFAULT 'running',
            params_json TEXT,
            notes TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS optimization_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            strategy_name TEXT,
            asset_class TEXT,
            window_name TEXT,
            train_start TEXT,
            train_end TEXT,
            test_start TEXT,
            test_end TEXT,
            parameters_json TEXT NOT NULL,
            total_return REAL,
            annual_return REAL,
            max_drawdown REAL,
            sharpe_ratio REAL,
            win_rate REAL,
            total_trades INTEGER,
            score_robustez REAL,
            warnings_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        cur.execute('CREATE INDEX IF NOT EXISTS ix_optimization_results_run ON optimization_results(run_id, score_robustez DESC)')
        self.conn.commit()

    def create_run(self, strategy_name: str, asset_class: str, start_date: str, end_date: str, mode: str, params: Dict[str, Any]) -> int:
        cur = self.conn.execute('''INSERT INTO optimization_runs(strategy_name, asset_class, start_date, end_date, mode, params_json)
                                   VALUES (?, ?, ?, ?, ?, ?)''',
                                (strategy_name, asset_class, start_date, end_date, mode, json.dumps(params, ensure_ascii=False)))
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str = 'success', notes: Optional[str] = None) -> None:
        self.conn.execute('UPDATE optimization_runs SET status=?, finished_at=CURRENT_TIMESTAMP, notes=? WHERE id=?', (status, notes, run_id))
        self.conn.commit()

    def insert_result(self, run_id: int, result: Dict[str, Any]) -> None:
        metrics = result.get('metrics', result)
        self.conn.execute('''INSERT INTO optimization_results(
            run_id, strategy_name, asset_class, window_name, train_start, train_end, test_start, test_end,
            parameters_json, total_return, annual_return, max_drawdown, sharpe_ratio, win_rate, total_trades,
            score_robustez, warnings_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (run_id, result.get('strategy_name'), result.get('asset_class'), result.get('window_name'),
             result.get('train_start'), result.get('train_end'), result.get('test_start'), result.get('test_end'),
             json.dumps(result.get('parameters', {}), ensure_ascii=False), metrics.get('total_return'),
             metrics.get('annual_return'), metrics.get('max_drawdown'), metrics.get('sharpe_ratio'),
             metrics.get('win_rate'), metrics.get('total_trades'), result.get('score_robustez'),
             json.dumps(result.get('warnings', []), ensure_ascii=False)))
        self.conn.commit()

    def latest_runs(self, limit: int = 5) -> List[dbcompat.Row]:
        return list(self.conn.execute('SELECT * FROM optimization_runs ORDER BY id DESC LIMIT ?', (limit,)))

    def best_results(self, run_id: Optional[int] = None, limit: int = 20) -> List[dbcompat.Row]:
        if run_id:
            return list(self.conn.execute('SELECT * FROM optimization_results WHERE run_id=? ORDER BY score_robustez DESC LIMIT ?', (run_id, limit)))
        return list(self.conn.execute('SELECT * FROM optimization_results ORDER BY id DESC LIMIT ?', (limit,)))
