from datetime import datetime
from dateutil.relativedelta import relativedelta

from db.database import get_connection


def inserir_despesa(dados):
    valor_parcela = float(dados["valor_parcela"])
    total_parcelas = int(dados["total_parcelas"])
    parcelas_pagas = int(dados.get("parcelas_pagas", 0))

    primeira_parcela = datetime.fromisoformat(dados["primeira_parcela"])

    parcelas_restantes = max(total_parcelas - parcelas_pagas, 0)

    valor_total = valor_parcela * total_parcelas
    valor_a_pagar = valor_parcela * parcelas_restantes

    # 📅 Datas automáticas
    ultimo_vencimento = primeira_parcela + relativedelta(months=total_parcelas - 1)
    proximo_vencimento = primeira_parcela + relativedelta(months=parcelas_pagas)

    hoje = datetime.today()

    atraso = 0
    if hoje > proximo_vencimento and parcelas_restantes > 0:
        atraso = (hoje - proximo_vencimento).days

    status = "Quitado" if parcelas_restantes == 0 else "Aberto"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO despesas (
            descricao,
            valor_parcela,
            primeira_parcela,
            total_parcelas,
            parcelas_pagas,
            parcelas_restantes,
            proximo_vencimento,
            ultimo_vencimento,
            atraso,
            valor_total,
            valor_a_pagar,
            situacao,
            tipo,
            mes,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dados["descricao"],
        valor_parcela,
        dados["primeira_parcela"],
        total_parcelas,
        parcelas_pagas,
        parcelas_restantes,
        proximo_vencimento.strftime("%Y-%m-%d"),
        ultimo_vencimento.strftime("%Y-%m-%d"),
        atraso,
        valor_total,
        valor_a_pagar,
        dados.get("situacao", "Pendente"),
        dados["tipo"],
        dados["mes"],
        status
    ))

    conn.commit()
    conn.close()