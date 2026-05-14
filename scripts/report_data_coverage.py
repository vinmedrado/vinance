from __future__ import annotations

from _cli_common import ROOT  # noqa: F401 - garante import path do projeto
from backend.app.data_layer.repositories.sqlite_repository import connect, coverage_by_asset, ensure_patch6_schema


def main() -> int:
    with connect() as conn:
        ensure_patch6_schema(conn)
        rows = coverage_by_asset(conn)

    total_com_dados = sum(1 for row in rows if int(row["total_registros"] or 0) > 0)
    total_sem_dados = sum(1 for row in rows if int(row["total_registros"] or 0) == 0)
    ativos_com_falha = [row["ticker"] for row in rows if int(row["total_registros"] or 0) == 0]

    print("\n" + "=" * 100)
    print("RELATÓRIO DE COBERTURA DE DADOS — FinanceOS")
    print("=" * 100)
    print(f"{'Ticker':<12} {'Classe':<10} {'Data inicial':<14} {'Data final':<14} {'Registros':<10} {'Dividendos':<10}")
    print("-" * 100)
    for row in rows:
        total = int(row["total_registros"] or 0)
        print(
            f"{row['ticker']:<12} "
            f"{row['asset_class']:<10} "
            f"{str(row['data_inicial'] or '-'): <14} "
            f"{str(row['data_final'] or '-'): <14} "
            f"{total:<10} "
            f"{'sim' if row['tem_dividendos'] else 'não':<10}"
        )
    print("-" * 100)
    print(f"Total de ativos com dados: {total_com_dados}")
    print(f"Ativos sem dados: {total_sem_dados}")
    print(f"Ativos com falha/sem cobertura: {', '.join(ativos_com_falha) if ativos_com_falha else '-'}")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
