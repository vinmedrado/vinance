import pandas as pd

from db.database import get_connection


EXCEL_PATH = "data/input/financas.xlsm"


def limpar_texto(valor):
    if pd.isna(valor):
        return None
    return str(valor).strip()


def importar_categorias(conn):
    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name="Conf",
        usecols="A:B",
        header=0
    )

    df.columns = ["descricao", "tipo"]
    df = df.dropna(how="all")
    df["descricao"] = df["descricao"].apply(limpar_texto)
    df["tipo"] = df["tipo"].apply(limpar_texto)
    df = df.dropna(subset=["descricao"])

    df.to_sql("categorias", conn, if_exists="replace", index=False)
    print(f"Categorias importadas: {len(df)}")


def importar_despesas(conn):
    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name="Despesas",
        usecols="C:Q",
        header=3
    )

    df.columns = [
        "descricao",
        "valor_parcela",
        "primeira_parcela",
        "total_parcelas",
        "parcelas_pagas",
        "parcelas_restantes",
        "proximo_vencimento",
        "ultimo_vencimento",
        "atraso",
        "valor_total",
        "valor_a_pagar",
        "situacao",
        "tipo",
        "mes",
        "status",
    ]

    df = df.dropna(how="all")
    df["descricao"] = df["descricao"].apply(limpar_texto)
    df = df.dropna(subset=["descricao"])

    df.to_sql("despesas", conn, if_exists="replace", index=False)
    print(f"Despesas importadas: {len(df)}")


def importar_planilha():
    conn = get_connection()

    importar_categorias(conn)
    importar_despesas(conn)

    conn.close()
    print("Importação concluída com sucesso.")


if __name__ == "__main__":
    importar_planilha()