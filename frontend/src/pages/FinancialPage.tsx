import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Badge, Button, Card, EmptyState, ErrorState, FormField, Input, LoadingState, MetricCard, MoneyInput, OnboardingCard, SectionHeader, SelectField, SubmitButton, Toast, ToggleField } from '../components';
import { useCreateExpense, useCreateIncome, useExpenses, useFinancialDiagnosis, useFinancialProfile, useIncomes } from '../features/financial/hooks/useFinancial';
import type { ApiErrorShape } from '../services/api';
import { formatCurrency, toNumber } from '../utils/formatters';

const today = () => new Date().toISOString().slice(0, 10);
const incomeTypeOptions = [
  { value: 'salario', label: 'Salário' }, { value: 'freelance', label: 'Freelance' }, { value: 'investimentos', label: 'Investimentos' }, { value: 'outros', label: 'Outros' },
];
const categoryOptions = [
  { value: 'moradia', label: 'Moradia' }, { value: 'alimentacao', label: 'Alimentação' }, { value: 'transporte', label: 'Transporte' }, { value: 'saude', label: 'Saúde' }, { value: 'educacao', label: 'Educação' }, { value: 'lazer', label: 'Lazer' }, { value: 'outros', label: 'Outros' },
];

function getActionError(...errors: unknown[]) { return errors.find(Boolean) as ApiErrorShape | null; }

export function FinancialPage() {
  const diagnosis = useFinancialDiagnosis();
  const incomes = useIncomes();
  const expenses = useExpenses();
  const profile = useFinancialProfile();
  const createIncome = useCreateIncome();
  const createExpense = useCreateExpense();
  const [incomeSaved, setIncomeSaved] = useState(false);
  const [expenseSaved, setExpenseSaved] = useState(false);
  const [showIncomeForm, setShowIncomeForm] = useState(false);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [income, setIncome] = useState({ description: '', amount: '', income_type: 'salario', received_at: today(), is_recurring: true });
  const [expense, setExpense] = useState({ description: '', amount: '', category: 'moradia', due_date: today(), paid_at: '', is_paid: false, is_recurring: true });
  const missingProfile = Boolean((profile.error as ApiErrorShape | null)?.status === 404 || (diagnosis.error as ApiErrorShape | null)?.status === 404);
  const error = !missingProfile ? getActionError(incomes.error, expenses.error, createIncome.error, createExpense.error, diagnosis.error, profile.error) : getActionError(incomes.error, expenses.error, createIncome.error, createExpense.error);

  useEffect(() => {
    if (!incomeSaved && !expenseSaved) return;
    const timer = window.setTimeout(() => { setIncomeSaved(false); setExpenseSaved(false); }, 3600);
    return () => window.clearTimeout(timer);
  }, [incomeSaved, expenseSaved]);

  const totals = useMemo(() => {
    const totalIncomes = incomes.data?.reduce((sum, item) => sum + toNumber(item.amount), 0) ?? 0;
    const totalExpenses = expenses.data?.reduce((sum, item) => sum + toNumber(item.amount), 0) ?? 0;
    const recurringIncomes = incomes.data?.filter((item) => item.is_recurring) ?? [];
    const recurringExpenses = expenses.data?.filter((item) => item.is_recurring) ?? [];
    return { incomes: totalIncomes, expenses: totalExpenses, balance: totalIncomes - totalExpenses, recurringIncomes, recurringExpenses };
  }, [incomes.data, expenses.data]);

  async function submitIncome(event: FormEvent) {
    event.preventDefault();
    if (createIncome.isPending) return;
    await createIncome.mutateAsync({ ...income, amount: Number(income.amount) });
    setIncome({ description: '', amount: '', income_type: 'salario', received_at: today(), is_recurring: true });
    setShowIncomeForm(false); setIncomeSaved(true);
  }

  async function submitExpense(event: FormEvent) {
    event.preventDefault();
    if (createExpense.isPending) return;
    await createExpense.mutateAsync({ ...expense, amount: Number(expense.amount), paid_at: expense.paid_at || null });
    setExpense({ description: '', amount: '', category: 'moradia', due_date: today(), paid_at: '', is_paid: false, is_recurring: true });
    setShowExpenseForm(false); setExpenseSaved(true);
  }

  function refetchFinancial() { profile.refetch(); diagnosis.refetch(); incomes.refetch(); expenses.refetch(); }

  return (
    <section className="vn-page">
      <SectionHeader eyebrow="Financeiro" title="Diagnóstico e orçamento real." description="Receitas, despesas e perfil financeiro conectados aos endpoints aprovados." />
      {error && <Card><ErrorState title="Ação financeira não concluída" description={error.message} action={<Button variant="secondary" onClick={refetchFinancial}>Recarregar dados</Button>} /></Card>}
      {incomeSaved && <Toast message="Receita cadastrada com sucesso." />}
      {expenseSaved && <Toast message="Despesa cadastrada com sucesso." />}
      {missingProfile && <OnboardingCard onCompleted={refetchFinancial} />}

      {!missingProfile && <div className="vn-metrics vn-metrics--refined">
        <MetricCard label="Total de receitas" value={formatCurrency(totals.incomes)} helper={`${incomes.data?.length ?? 0} entradas cadastradas`} badge={`${totals.recurringIncomes.length} recorrentes`} />
        <MetricCard label="Total de despesas" value={formatCurrency(totals.expenses)} helper={`${expenses.data?.length ?? 0} saídas cadastradas`} badge={`${totals.recurringExpenses.length} recorrentes`} tone={totals.expenses > totals.incomes ? 'warning' : 'neutral'} />
        <MetricCard label="Saldo estimado" value={formatCurrency(totals.balance)} helper="Receitas menos despesas cadastradas." badge={totals.balance >= 0 ? 'positivo' : 'atenção'} tone={totals.balance >= 0 ? 'success' : 'warning'} />
      </div>}

      <div className="vn-grid vn-grid--two">
        <Card title="Receitas" description="Entradas que alimentam orçamento, score e capacidade de aporte." action={<Button variant="secondary" onClick={() => setShowIncomeForm((value) => !value)}>{showIncomeForm ? 'Fechar' : 'Nova receita'}</Button>}>
          {!showIncomeForm && incomes.data?.length === 0 && <EmptyState title="Nenhuma receita cadastrada" description="Cadastre sua primeira receita para o Vinance calcular seu orçamento com mais precisão." action={<Button onClick={() => setShowIncomeForm(true)}>Cadastrar primeira receita</Button>} />}
          {showIncomeForm && <form className="vn-form vn-compact-form" onSubmit={submitIncome}>
            <Input label="Descrição" placeholder="Ex.: Salário CLT" value={income.description} onChange={(event) => setIncome({ ...income, description: event.target.value })} required />
            <MoneyInput label="Valor" value={income.amount} onChange={(event) => setIncome({ ...income, amount: event.target.value })} required />
            <SelectField label="Tipo" value={income.income_type} onChange={(event) => setIncome({ ...income, income_type: event.target.value })} options={incomeTypeOptions} />
            <FormField label="Data de recebimento"><input className="vn-input" type="date" value={income.received_at} onChange={(event) => setIncome({ ...income, received_at: event.target.value })} required /></FormField>
            <ToggleField label="Receita recorrente" checked={income.is_recurring} onChange={(event) => setIncome({ ...income, is_recurring: event.target.checked })} />
            <SubmitButton loading={createIncome.isPending}>Salvar receita</SubmitButton>
          </form>}
          {incomes.isLoading ? <LoadingState label="Carregando receitas..." /> : <div className="vn-list vn-section-gap">{incomes.data?.map((item) => <div key={item.id}><strong>{item.description} <Badge>{item.is_recurring ? 'recorrente' : 'pontual'}</Badge></strong><span>{formatCurrency(item.amount)} · {item.income_type} · {item.received_at}</span></div>)}</div>}
        </Card>

        <Card title="Despesas" description="Saídas usadas para calcular comprometimento de renda e prioridade de reserva." action={<Button variant="secondary" onClick={() => setShowExpenseForm((value) => !value)}>{showExpenseForm ? 'Fechar' : 'Nova despesa'}</Button>}>
          {!showExpenseForm && expenses.data?.length === 0 && <EmptyState title="Nenhuma despesa cadastrada" description="Cadastre sua primeira despesa para entender comprometimento de renda e capacidade de aporte." action={<Button onClick={() => setShowExpenseForm(true)}>Cadastrar primeira despesa</Button>} />}
          {showExpenseForm && <form className="vn-form vn-compact-form" onSubmit={submitExpense}>
            <Input label="Descrição" placeholder="Ex.: Aluguel" value={expense.description} onChange={(event) => setExpense({ ...expense, description: event.target.value })} required />
            <MoneyInput label="Valor" value={expense.amount} onChange={(event) => setExpense({ ...expense, amount: event.target.value })} required />
            <SelectField label="Categoria" value={expense.category} onChange={(event) => setExpense({ ...expense, category: event.target.value })} options={categoryOptions} />
            <FormField label="Vencimento"><input className="vn-input" type="date" value={expense.due_date} onChange={(event) => setExpense({ ...expense, due_date: event.target.value })} required /></FormField>
            <FormField label="Pagamento"><input className="vn-input" type="date" value={expense.paid_at} onChange={(event) => setExpense({ ...expense, paid_at: event.target.value })} /></FormField>
            <ToggleField label="Despesa paga" checked={expense.is_paid} onChange={(event) => setExpense({ ...expense, is_paid: event.target.checked })} />
            <ToggleField label="Despesa recorrente" checked={expense.is_recurring} onChange={(event) => setExpense({ ...expense, is_recurring: event.target.checked })} />
            <SubmitButton loading={createExpense.isPending}>Salvar despesa</SubmitButton>
          </form>}
          {expenses.isLoading ? <LoadingState label="Carregando despesas..." /> : <div className="vn-list vn-section-gap">{expenses.data?.map((item) => <div key={item.id}><strong>{item.description} <Badge tone={item.is_paid ? 'success' : 'warning'}>{item.is_paid ? 'paga' : 'pendente'}</Badge><Badge>{item.is_recurring ? 'recorrente' : 'pontual'}</Badge></strong><span>{formatCurrency(item.amount)} · {item.category} · vence em {item.due_date}</span></div>)}</div>}
        </Card>
      </div>
    </section>
  );
}
