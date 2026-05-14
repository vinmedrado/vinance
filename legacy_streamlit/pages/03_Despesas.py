from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
from services.financial_crud_service import (
    create_transaction,
    delete_transaction,
    list_transactions,
    money,
    month_ref,
    seed_demo_if_empty,
    summarize_month,
    update_transaction_status,
)
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_empty_state, render_callout, render_badge

st.set_page_config(page_title="FinanceOS · Despesas", layout="wide")
inject_global_css()
check_auth()

try:
    seed_demo_if_empty()
except Exception as exc:
    render_callout("Banco financeiro indisponível", "Configure DATABASE_URL/SYNC_DATABASE_URL e rode as migrations. A página não exibe stack trace para o usuário final.", "warning")
    st.stop()

render_hero(
    "Despesas com CRUD real",
    "Cadastre, liste, marque como pago e exclua despesas usando banco real. Esses dados alimentam orçamento, diagnóstico e sugestão de investimento.",
    eyebrow="ERP Financeiro",
    status="Persistência em PostgreSQL via SQLAlchemy · sem depender de session_state/mock",
)

with st.container(border=True):
    st.subheader("Nova despesa")
    c1, c2, c3 = st.columns(3)
    with c1:
        valor = st.number_input("Valor", min_value=0.0, step=10.0)
        descricao = st.text_input("Descrição", placeholder="Ex.: Mercado, aluguel, assinatura...")
        categoria = st.selectbox("Categoria", ["Necessidades", "Desejos", "Investimentos/Reserva", "Metas", "Outros"])
    with c2:
        subcategoria = st.text_input("Subcategoria", placeholder="Ex.: Alimentação")
        data_lanc = st.date_input("Data", value=date.today())
        recorrencia = st.selectbox("Recorrência", ["Única", "Mensal", "Semanal", "Anual"])
    with c3:
        forma = st.selectbox("Forma de pagamento", ["PIX", "Débito", "Crédito", "Boleto", "Dinheiro", "Transferência"])
        conta = st.text_input("Conta/Cartão", placeholder="Ex.: Conta principal, Visa...")
        status = st.selectbox("Status", ["Pago", "Pendente", "Vencido"])
    tags = st.text_input("Tags", placeholder="casa, essencial, recorrente")
    obs = st.text_area("Observações", placeholder="Comprovante/anexo poderá ser ligado em versão futura.")

    b1, b2 = st.columns([.25, .75])
    with b1:
        if st.button("Salvar", type="primary", use_container_width=True):
            try:
                tx_type = "investment" if categoria == "Investimentos/Reserva" else "expense"
                create_transaction({
                    "transaction_type": tx_type,
                    "amount": valor,
                    "description": descricao,
                    "category": categoria,
                    "subcategory": subcategoria,
                    "transaction_date": data_lanc,
                    "recurrence": recorrencia,
                    "payment_method": forma,
                    "account_name": conta,
                    "status": status,
                    "tags": tags,
                    "notes": obs,
                })
                st.success("Despesa salva no banco com sucesso.")
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))
            except Exception:
                st.error("Não foi possível salvar agora. Verifique a conexão com o banco.")
    with b2:
        if st.button("Salvar e adicionar outra", use_container_width=True):
            st.info("Use Salvar para persistir e mantenha o fluxo de cadastro rápido.")

selected_month = st.text_input("Mês de referência", value=month_ref(), help="Formato YYYY-MM")
summary = summarize_month(month=selected_month)
render_section_header("Resumo do mês")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: render_metric_card("Total gasto", money(summary['expenses'] + summary['invested']), color="red")
with c2: render_metric_card("Despesas", money(summary['expenses']), color="yellow")
with c3: render_metric_card("Investimentos", money(summary['invested']), color="green")
with c4: render_metric_card("Pendentes", money(summary['pending']), color="yellow")
with c5: render_metric_card("Vencidas", money(summary['overdue']), color="red")
with c6: render_metric_card("Maior categoria", summary['biggest_category'], color="purple")

render_section_header("Listagem premium", "Filtre, acompanhe status e faça ações rápidas sem expor complexidade técnica.")
f1, f2, f3, f4 = st.columns(4)
with f1: cat_filter = st.selectbox("Categoria", ["Todas", "Necessidades", "Desejos", "Investimentos/Reserva", "Metas", "Outros"])
with f2: status_filter = st.selectbox("Status", ["Todos", "Pago", "Pendente", "Vencido"])
with f3: search = st.text_input("Buscar", placeholder="Descrição, tag ou conta")
with f4: st.page_link("legacy_streamlit/pages/04_Orcamento.py", label="Ver orçamento", icon="📊")

rows = list_transactions(month=selected_month)
if cat_filter != "Todas":
    rows = [r for r in rows if r.get("category") == cat_filter]
if status_filter != "Todos":
    rows = [r for r in rows if r.get("status") == status_filter]
if search:
    s = search.lower()
    rows = [r for r in rows if s in str(r.get("description", "")).lower() or s in str(r.get("tags", "")).lower() or s in str(r.get("account_name", "")).lower()]

if not rows:
    render_empty_state("Nenhuma despesa encontrada", "Cadastre sua primeira despesa para ativar orçamento, diagnóstico e alertas financeiros.", "Cadastrar agora", "legacy_streamlit/pages/03_Despesas.py")
else:
    df = pd.DataFrame(rows)
    view = df[["id", "transaction_date", "description", "category", "subcategory", "amount", "payment_method", "account_name", "status", "tags"]].copy()
    view.columns = ["ID", "Data", "Descrição", "Categoria", "Subcategoria", "Valor", "Forma", "Conta/Cartão", "Status", "Tags"]
    view["Valor"] = view["Valor"].map(money)
    st.dataframe(view, use_container_width=True, hide_index=True)

    render_section_header("Ações rápidas")
    a1, a2, a3 = st.columns(3)
    selected_id = a1.number_input("ID da despesa", min_value=0, step=1)
    if a2.button("Marcar como pago", use_container_width=True):
        if selected_id:
            update_transaction_status(int(selected_id), "Pago")
            st.success("Status atualizado.")
            st.rerun()
    if a3.button("Excluir lançamento", use_container_width=True):
        if selected_id:
            delete_transaction(int(selected_id))
            st.success("Lançamento excluído.")
            st.rerun()
