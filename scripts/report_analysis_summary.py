from __future__ import annotations
from db import pg_compat as dbcompat, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from backend.app.analysis.analysis_repository import ROOT_DIR, ensure_analysis_schema

def main() -> int:
    with dbcompat.connect(ROOT_DIR) as conn:
        conn.row_factory=dbcompat.Row; ensure_analysis_schema(conn)
        print('='*80); print('FinanceOS - Resumo da Análise Financeira'); print('='*80)
        print(f"Métricas calculadas: {conn.execute('SELECT COUNT(*) FROM asset_analysis_metrics').fetchone()[0]}")
        print(f"Scores calculados: {conn.execute('SELECT COUNT(*) FROM asset_scores').fetchone()[0]}")
        print(f"Rankings gerados: {conn.execute('SELECT COUNT(*) FROM asset_rankings').fetchone()[0]}")
        print('\nScores por classe:')
        for row in conn.execute('SELECT asset_class, COUNT(*) qtd, ROUND(AVG(score_total),2) media FROM asset_scores GROUP BY asset_class ORDER BY qtd DESC'):
            print(f"- {row['asset_class']}: {row['qtd']} ativos | score médio {row['media']}")
        print('\nTop ranking geral por classe:')
        for row in conn.execute("SELECT asset_class,ticker,score_value,rank_position FROM asset_rankings WHERE ranking_type='score_total' AND rank_position<=5 ORDER BY asset_class,rank_position"):
            print(f"- {row['asset_class']} #{row['rank_position']}: {row['ticker']} ({row['score_value']})")
        last=conn.execute('SELECT * FROM analysis_run_logs ORDER BY id DESC LIMIT 1').fetchone()
        if last: print(f"\nÚltima execução: status={last['status']} | total={last['total_assets']} | sucesso={last['total_success']} | falhas={last['total_failed']} | ignorados={last['total_skipped']}")
    return 0
if __name__ == '__main__': raise SystemExit(main())
