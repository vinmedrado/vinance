from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from db.database import SessionLocal, sync_engine

DEFAULT_USER_ID = "demo-user"

ERP_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS erp_categories (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL DEFAULT 'demo-user',
        name VARCHAR(160) NOT NULL,
        kind VARCHAR(40) NOT NULL DEFAULT 'expense',
        budget_group VARCHAR(80) DEFAULT 'Necessidades',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_accounts (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL DEFAULT 'demo-user',
        name VARCHAR(160) NOT NULL,
        account_type VARCHAR(60) NOT NULL DEFAULT 'Conta corrente',
        balance NUMERIC(14,2) NOT NULL DEFAULT 0,
        institution VARCHAR(120),
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_cards (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL DEFAULT 'demo-user',
        name VARCHAR(160) NOT NULL,
        limit_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
        closing_day INTEGER,
        due_day INTEGER,
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_transactions (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL DEFAULT 'demo-user',
        transaction_type VARCHAR(20) NOT NULL,
        amount NUMERIC(14,2) NOT NULL,
        description VARCHAR(255) NOT NULL,
        category VARCHAR(120) NOT NULL DEFAULT 'Outros',
        subcategory VARCHAR(120),
        transaction_date DATE NOT NULL,
        recurrence VARCHAR(40) DEFAULT 'Única',
        payment_method VARCHAR(80),
        account_name VARCHAR(160),
        card_name VARCHAR(160),
        status VARCHAR(40) DEFAULT 'Pendente',
        tags VARCHAR(255),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_budget_profiles (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL DEFAULT 'demo-user',
        model_name VARCHAR(80) NOT NULL DEFAULT '50/30/20',
        monthly_income NUMERIC(14,2) NOT NULL DEFAULT 0,
        custom_needs_pct NUMERIC(8,4),
        custom_wants_pct NUMERIC(8,4),
        custom_invest_pct NUMERIC(8,4),
        active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_goals (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL DEFAULT 'demo-user',
        name VARCHAR(160) NOT NULL,
        target_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
        current_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
        target_date DATE,
        status VARCHAR(40) DEFAULT 'Ativa',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS erp_planned_investments (
        id SERIAL PRIMARY KEY,
        user_id VARCHAR(120) NOT NULL DEFAULT 'demo-user',
        name VARCHAR(160) NOT NULL,
        target_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
        actual_amount NUMERIC(14,2) NOT NULL DEFAULT 0,
        month_ref VARCHAR(7) NOT NULL,
        asset_class VARCHAR(80) DEFAULT 'Carteira',
        status VARCHAR(40) DEFAULT 'Planejado',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

SQLITE_TABLES_SQL = [sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT").replace("BOOLEAN", "INTEGER").replace("NUMERIC(14,2)", "REAL").replace("NUMERIC(8,4)", "REAL").replace("TIMESTAMP", "TEXT").replace("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP") for sql in ERP_TABLES_SQL]

BUDGET_MODELS: dict[str, dict[str, float]] = {
    "50/30/20": {"Necessidades": 0.50, "Desejos": 0.30, "Investimentos/Reserva": 0.20},
    "70/20/10": {"Necessidades": 0.70, "Investimentos/Reserva": 0.20, "Desejos": 0.10},
    "60/30/10": {"Necessidades": 0.60, "Desejos": 0.30, "Investimentos/Reserva": 0.10},
    "Base Zero": {"Planejado manualmente": 1.00},
    "Personalizado": {"Necessidades": 0.45, "Desejos": 0.25, "Investimentos/Reserva": 0.20, "Metas": 0.10},
    "Personalizado Premium": {"Necessidades": 0.45, "Desejos": 0.25, "Investimentos/Reserva": 0.20, "Metas": 0.10},
}


def _is_sqlite() -> bool:
    return str(sync_engine.url).startswith("sqlite")


def ensure_erp_schema() -> None:
    ddl = SQLITE_TABLES_SQL if _is_sqlite() else ERP_TABLES_SQL
    with sync_engine.begin() as conn:
        for sql in ddl:
            conn.execute(text(sql))
        # índices úteis, não críticos caso o banco bloqueie algum dialeto.
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_erp_transactions_user_date ON erp_transactions(user_id, transaction_date)",
            "CREATE INDEX IF NOT EXISTS idx_erp_transactions_type_status ON erp_transactions(transaction_type, status)",
            "CREATE INDEX IF NOT EXISTS idx_erp_budget_profiles_user_active ON erp_budget_profiles(user_id, active)",
        ]:
            try:
                conn.execute(text(idx))
            except Exception:
                pass


@contextmanager
def session_scope():
    ensure_erp_schema()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def money(value: float | int | None) -> str:
    value = float(value or 0)
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def month_ref(d: date | None = None) -> str:
    d = d or date.today()
    return f"{d.year:04d}-{d.month:02d}"


def _row_to_dict(row: Any) -> Dict[str, Any]:
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def list_transactions(user_id: str = DEFAULT_USER_ID, transaction_type: str | None = None, month: str | None = None, status: str | None = None) -> List[Dict[str, Any]]:
    ensure_erp_schema()
    query = "SELECT * FROM erp_transactions WHERE user_id=:user_id"
    params: dict[str, Any] = {"user_id": user_id}
    if transaction_type:
        query += " AND transaction_type=:transaction_type"
        params["transaction_type"] = transaction_type
    if month:
        query += " AND TO_CHAR(transaction_date, 'YYYY-MM')=:month" if not _is_sqlite() else " AND strftime('%Y-%m', transaction_date)=:month"
        params["month"] = month
    if status and status != "Todos":
        query += " AND status=:status"
        params["status"] = status
    query += " ORDER BY transaction_date DESC, id DESC"
    with session_scope() as session:
        return [_row_to_dict(r) for r in session.execute(text(query), params).fetchall()]


def create_transaction(data: Dict[str, Any], user_id: str = DEFAULT_USER_ID) -> int:
    ensure_erp_schema()
    payload = {
        "user_id": user_id,
        "transaction_type": data.get("transaction_type", "expense"),
        "amount": float(data.get("amount") or data.get("valor") or 0),
        "description": str(data.get("description") or data.get("descricao") or "").strip(),
        "category": data.get("category") or data.get("categoria") or "Outros",
        "subcategory": data.get("subcategory") or data.get("subcategoria") or "",
        "transaction_date": data.get("transaction_date") or data.get("data") or date.today(),
        "recurrence": data.get("recurrence") or data.get("recorrencia") or "Única",
        "payment_method": data.get("payment_method") or data.get("forma") or "PIX",
        "account_name": data.get("account_name") or data.get("conta") or "Conta principal",
        "card_name": data.get("card_name") or data.get("cartao") or "",
        "status": data.get("status") or "Pendente",
        "tags": data.get("tags") or "",
        "notes": data.get("notes") or data.get("observacoes") or "",
    }
    if not payload["description"] or payload["amount"] <= 0:
        raise ValueError("Informe descrição e valor maior que zero.")
    returning = " RETURNING id" if not _is_sqlite() else ""
    sql = text("""
        INSERT INTO erp_transactions
        (user_id, transaction_type, amount, description, category, subcategory, transaction_date, recurrence, payment_method, account_name, card_name, status, tags, notes)
        VALUES (:user_id, :transaction_type, :amount, :description, :category, :subcategory, :transaction_date, :recurrence, :payment_method, :account_name, :card_name, :status, :tags, :notes)
    """ + returning)
    with session_scope() as session:
        result = session.execute(sql, payload)
        if _is_sqlite():
            return int(session.execute(text("SELECT last_insert_rowid()")).scalar() or 0)
        return int(result.scalar() or 0)


def update_transaction_status(transaction_id: int, status: str, user_id: str = DEFAULT_USER_ID) -> None:
    with session_scope() as session:
        session.execute(text("UPDATE erp_transactions SET status=:status, updated_at=CURRENT_TIMESTAMP WHERE id=:id AND user_id=:user_id"), {"status": status, "id": transaction_id, "user_id": user_id})


def delete_transaction(transaction_id: int, user_id: str = DEFAULT_USER_ID) -> None:
    with session_scope() as session:
        session.execute(text("DELETE FROM erp_transactions WHERE id=:id AND user_id=:user_id"), {"id": transaction_id, "user_id": user_id})


def upsert_budget_profile(model_name: str, monthly_income: float, user_id: str = DEFAULT_USER_ID) -> None:
    ensure_erp_schema()
    with session_scope() as session:
        session.execute(text("UPDATE erp_budget_profiles SET active=false WHERE user_id=:user_id"), {"user_id": user_id})
        session.execute(text("""
            INSERT INTO erp_budget_profiles (user_id, model_name, monthly_income, active)
            VALUES (:user_id, :model_name, :monthly_income, true)
        """), {"user_id": user_id, "model_name": model_name, "monthly_income": float(monthly_income or 0)})


def get_budget_profile(user_id: str = DEFAULT_USER_ID) -> Dict[str, Any]:
    ensure_erp_schema()
    with session_scope() as session:
        row = session.execute(text("SELECT * FROM erp_budget_profiles WHERE user_id=:user_id AND active=true ORDER BY id DESC LIMIT 1"), {"user_id": user_id}).fetchone()
        if row:
            return _row_to_dict(row)
    return {"model_name": "50/30/20", "monthly_income": 0.0}


def list_accounts(user_id: str = DEFAULT_USER_ID) -> List[Dict[str, Any]]:
    ensure_erp_schema()
    with session_scope() as session:
        return [_row_to_dict(r) for r in session.execute(text("SELECT * FROM erp_accounts WHERE user_id=:user_id ORDER BY name"), {"user_id": user_id}).fetchall()]


def list_goals(user_id: str = DEFAULT_USER_ID) -> List[Dict[str, Any]]:
    ensure_erp_schema()
    with session_scope() as session:
        return [_row_to_dict(r) for r in session.execute(text("SELECT * FROM erp_goals WHERE user_id=:user_id ORDER BY created_at DESC"), {"user_id": user_id}).fetchall()]


def create_goal(name: str, target_amount: float, current_amount: float = 0, user_id: str = DEFAULT_USER_ID) -> None:
    with session_scope() as session:
        session.execute(text("INSERT INTO erp_goals (user_id, name, target_amount, current_amount) VALUES (:user_id, :name, :target_amount, :current_amount)"), {"user_id": user_id, "name": name, "target_amount": target_amount, "current_amount": current_amount})


def summarize_month(user_id: str = DEFAULT_USER_ID, month: str | None = None) -> Dict[str, Any]:
    month = month or month_ref()
    rows = list_transactions(user_id=user_id, month=month)
    income = sum(float(r.get("amount") or 0) for r in rows if r.get("transaction_type") == "income")
    expenses = sum(float(r.get("amount") or 0) for r in rows if r.get("transaction_type") == "expense")
    invested = sum(float(r.get("amount") or 0) for r in rows if r.get("transaction_type") == "investment" or "Investimentos" in str(r.get("category")))
    pending = sum(float(r.get("amount") or 0) for r in rows if r.get("status") == "Pendente")
    overdue = sum(float(r.get("amount") or 0) for r in rows if r.get("status") == "Vencido")
    by_category: dict[str, float] = {}
    for r in rows:
        if r.get("transaction_type") in {"expense", "investment"}:
            by_category[str(r.get("category") or "Outros")] = by_category.get(str(r.get("category") or "Outros"), 0.0) + float(r.get("amount") or 0)
    biggest = max(by_category.items(), key=lambda item: item[1])[0] if by_category else "-"
    budget = get_budget_profile(user_id)
    income_base = float(budget.get("monthly_income") or income or 0)
    recommended_investment = income_base * _investment_pct(str(budget.get("model_name") or "50/30/20"))
    return {
        "month": month,
        "rows": rows,
        "income": income,
        "income_base": income_base,
        "expenses": expenses,
        "invested": invested,
        "pending": pending,
        "overdue": overdue,
        "balance": income - expenses - invested,
        "available_to_invest": max(income - expenses - invested, 0),
        "percent_invested": (invested / income_base * 100) if income_base else 0,
        "recommended_investment": recommended_investment,
        "investment_gap": invested - recommended_investment,
        "by_category": by_category,
        "biggest_category": biggest,
        "budget_model": budget.get("model_name", "50/30/20"),
    }


def _investment_pct(model: str) -> float:
    values = BUDGET_MODELS.get(model, BUDGET_MODELS["50/30/20"])
    for key, pct in values.items():
        if "Invest" in key:
            return pct
    return 0.0


def calculate_budget(model: str, monthly_income: float, realized_by_category: dict[str, float] | None = None) -> List[Dict[str, Any]]:
    percents = BUDGET_MODELS.get(model, BUDGET_MODELS["50/30/20"])
    realized_by_category = realized_by_category or {}
    rows: list[dict[str, Any]] = []
    for category, pct in percents.items():
        planned = float(monthly_income or 0) * pct
        if "Investimentos" in category:
            realized = sum(v for k, v in realized_by_category.items() if "Invest" in k)
        elif category == "Planejado manualmente":
            realized = sum(realized_by_category.values())
        else:
            realized = sum(v for k, v in realized_by_category.items() if k == category)
        rows.append({
            "Categoria": category,
            "Percentual": pct,
            "Planejado": planned,
            "Realizado": realized,
            "Diferença": planned - realized,
            "Status": "Dentro do plano" if realized <= planned else "Acima do limite",
        })
    return rows


def seed_demo_if_empty(user_id: str = DEFAULT_USER_ID) -> None:
    ensure_erp_schema()
    if list_transactions(user_id=user_id, month=month_ref()):
        return
    today = date.today()
    defaults = [
        {"transaction_type":"income", "amount":6500, "description":"Salário", "category":"Receitas", "transaction_date":today, "status":"Recebido", "payment_method":"Transferência", "account_name":"Conta principal"},
        {"transaction_type":"expense", "amount":1800, "description":"Aluguel", "category":"Necessidades", "subcategory":"Moradia", "transaction_date":today, "status":"Pago", "payment_method":"PIX", "account_name":"Conta principal"},
        {"transaction_type":"expense", "amount":720, "description":"Mercado", "category":"Necessidades", "subcategory":"Alimentação", "transaction_date":today, "status":"Pendente", "payment_method":"Crédito", "account_name":"Cartão Visa"},
        {"transaction_type":"expense", "amount":260, "description":"Lazer", "category":"Desejos", "subcategory":"Entretenimento", "transaction_date":today, "status":"Pago", "payment_method":"Débito", "account_name":"Conta principal"},
        {"transaction_type":"investment", "amount":650, "description":"Aporte mensal", "category":"Investimentos/Reserva", "subcategory":"Carteira", "transaction_date":today, "status":"Pago", "payment_method":"Transferência", "account_name":"Corretora"},
    ]
    for item in defaults:
        create_transaction(item, user_id=user_id)
    upsert_budget_profile("50/30/20", 6500, user_id=user_id)
