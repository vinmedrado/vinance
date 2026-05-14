from db.database import get_connection


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        tipo TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT,
        valor_parcela REAL,
        primeira_parcela TEXT,
        total_parcelas INTEGER,
        parcelas_pagas INTEGER,
        parcelas_restantes INTEGER,
        proximo_vencimento TEXT,
        ultimo_vencimento TEXT,
        atraso INTEGER,
        valor_total REAL,
        valor_a_pagar REAL,
        situacao TEXT,
        tipo TEXT,
        mes TEXT,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    create_tables()
    print("Tabelas criadas/verificadas com sucesso.")