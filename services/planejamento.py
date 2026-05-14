from datetime import datetime
import pandas as pd


def sugerir_metodo(total_parcelas_30_dias: float, saldo: float):
    if saldo <= 0:
        return {
            "metodo": None,
            "perc_necessidade": 0,
            "perc_desejos": 0,
            "perc_investimento": 0,
        }

    proporcao = total_parcelas_30_dias / saldo

    if proporcao > 0.6:
        return {
            "metodo": "80/15/5",
            "perc_necessidade": 0.80,
            "perc_desejos": 0.15,
            "perc_investimento": 0.05,
        }

    if proporcao > 0.4:
        return {
            "metodo": "70/20/10",
            "perc_necessidade": 0.70,
            "perc_desejos": 0.20,
            "perc_investimento": 0.10,
        }

    return {
        "metodo": "50/30/20",
        "perc_necessidade": 0.50,
        "perc_desejos": 0.30,
        "perc_investimento": 0.20,
    }


def calcular_prioridade(proximo_vencimento, valor_parcela: float, saldo: float):
    hoje = datetime.today().date()

    if pd.isna(proximo_vencimento):
        return "Baixa"

    vencimento = pd.to_datetime(proximo_vencimento).date()
    dias = (vencimento - hoje).days

    proporcao = valor_parcela / saldo if saldo > 0 else 0

    if vencimento < hoje:
        return "Alta"

    if dias <= 10 or proporcao > 0.20:
        return "Alta"

    if dias <= 20 or proporcao > 0.10:
        return "Média"

    return "Baixa"


def gerar_planejamento(df: pd.DataFrame, saldo: float):
    if df.empty:
        return {
            "total_30_dias": 0,
            "metodo": sugerir_metodo(0, saldo),
            "valores_sugeridos": {
                "Necessidade": 0,
                "Desejos": 0,
                "Investimento": 0,
            },
            "contas": pd.DataFrame(),
            "resumo_prioridade": {
                "Alta": 0,
                "Média": 0,
                "Baixa": 0,
            },
        }

    base = df.copy()
    base["proximo_vencimento"] = pd.to_datetime(base["proximo_vencimento"], errors="coerce")
    base["valor_parcela"] = pd.to_numeric(base["valor_parcela"], errors="coerce").fillna(0)

    hoje = pd.Timestamp.today().normalize()
    limite = hoje + pd.Timedelta(days=30)

    contas_30 = base[
        (base["proximo_vencimento"].notna()) &
        (base["proximo_vencimento"] <= limite) &
        (base["status"] != "Quitado")
    ].copy()

    total_30 = contas_30["valor_parcela"].sum()

    metodo = sugerir_metodo(total_30, saldo)

    valores_sugeridos = {
        "Necessidade": saldo * metodo["perc_necessidade"],
        "Desejos": saldo * metodo["perc_desejos"],
        "Investimento": saldo * metodo["perc_investimento"],
    }

    if not contas_30.empty:
        contas_30["prioridade"] = contas_30.apply(
            lambda row: calcular_prioridade(
                row["proximo_vencimento"],
                row["valor_parcela"],
                saldo
            ),
            axis=1
        )

        prioridade_ordem = {"Alta": 0, "Média": 1, "Baixa": 2}
        contas_30["ordem_prioridade"] = contas_30["prioridade"].map(prioridade_ordem)

        contas_30 = contas_30.sort_values(
            by=["ordem_prioridade", "proximo_vencimento"]
        )

    resumo_prioridade = {
        "Alta": contas_30.loc[contas_30["prioridade"] == "Alta", "valor_parcela"].sum() if not contas_30.empty else 0,
        "Média": contas_30.loc[contas_30["prioridade"] == "Média", "valor_parcela"].sum() if not contas_30.empty else 0,
        "Baixa": contas_30.loc[contas_30["prioridade"] == "Baixa", "valor_parcela"].sum() if not contas_30.empty else 0,
    }

    return {
        "total_30_dias": total_30,
        "metodo": metodo,
        "valores_sugeridos": valores_sugeridos,
        "contas": contas_30,
        "resumo_prioridade": resumo_prioridade,
    }