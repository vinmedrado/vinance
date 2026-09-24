import { FormEvent, useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  FormField,
  Input,
  LoadingState,
  MetricCard,
  MoneyInput,
  OnboardingCard,
  SectionHeader,
  SelectField,
  SubmitButton,
  Toast,
  ToggleField,
} from '../components';
import {
  useActionPlanDecision,
  useActionPlanHistory,
  useCapitalAllocationHistory,
  useCreateCapitalAllocationDecision,
  useCreateActionPlanDecision,
  useCreateFinancialPolicyDecision,
  useCreateHouseholdExpense,
  useCreateHouseholdIncome,
  useCreateFinancialStateSnapshot,
  useCreateInvestmentOrchestrationDecision,
  useCurrentCapitalAllocation,
  useCurrentActionPlan,
  useCurrentFinancialPolicy,
  useCurrentFinancialState,
  useCurrentInvestmentOrchestration,
  useDefaultHousehold,
  useFinancialPolicyHistory,
  useHouseholdExpenses,
  useHouseholdIncomes,
  useHouseholds,
  useInvestmentOrchestrationHistory,
} from '../features/financial-state/hooks/useFinancialState';
import { ActionPlanCard } from '../features/financial-state/components/ActionPlanCard';
import { FinancialPolicyCard } from '../features/financial-state/components/FinancialPolicyCard';
import { CapitalAllocationCard } from '../features/financial-state/components/CapitalAllocationCard';
import { InvestmentOrchestrationCard } from '../features/financial-state/components/InvestmentOrchestrationCard';
import type { DataQuality, MoneyValue, OwnershipScope } from '../features/financial-state/types/financialState.types';
import { useFinancialProfile } from '../features/financial/hooks/useFinancial';
import type { ApiErrorShape } from '../services/api';
import { formatCurrency, formatPercent } from '../utils/formatters';

const today = () => new Date().toISOString().slice(0, 10);
const incomeTypeOptions = [
  { value: 'salario', label: 'Salário' },
  { value: 'freelance', label: 'Freelance' },
  { value: 'investimentos', label: 'Investimentos' },
  { value: 'outros', label: 'Outros' },
];
const categoryOptions = [
  { value: 'moradia', label: 'Moradia' },
  { value: 'alimentacao', label: 'Alimentação' },
  { value: 'transporte', label: 'Transporte' },
  { value: 'saude', label: 'Saúde' },
  { value: 'educacao', label: 'Educação' },
  { value: 'lazer', label: 'Lazer' },
  { value: 'outros', label: 'Outros' },
];
const ownershipOptions = [
  { value: 'PERSONAL', label: 'Pessoal' },
  { value: 'HOUSEHOLD', label: 'Compartilhada no household' },
];
const expenseNatureOptions = [
  { value: 'FIXED', label: 'Fixa' },
  { value: 'VARIABLE', label: 'Variável' },
];
const assetClassLabels: Record<string, string> = {
  CASH: 'Dinheiro e conta',
  EMERGENCY_RESERVE: 'Reserva de emergência',
  FIXED_INCOME: 'Renda fixa',
  INVESTMENTS: 'Investimentos',
  REAL_ESTATE: 'Imóveis',
  VEHICLES: 'Veículos',
  OTHER: 'Outros',
};

function getActionError(...errors: unknown[]) {
  return errors.find(Boolean) as ApiErrorShape | null;
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  if (error && typeof error === 'object' && 'message' in error) return String(error.message);
  return 'Tente novamente em alguns instantes.';
}

const qualityLabels: Record<DataQuality, string> = {
  COMPLETE: 'Completa',
  PARTIAL: 'Parcial',
  INSUFFICIENT: 'Insuficiente',
  STALE: 'Desatualizada',
  INCONSISTENT: 'Inconsistente',
};

const missingLabels: Record<string, string> = {
  'income.non_recurring': 'Renda não recorrente deste mês',
  'expenses.monthly': 'Despesas deste mês',
  'expenses.fixed': 'Despesas fixas deste mês',
  'expenses.variable': 'Despesas variáveis deste mês',
  'assets.current_value': 'Valor atual do patrimônio',
  'assets.emergency_reserve': 'Reserva de emergência atual',
  'liabilities.current_balance': 'Saldo atual das dívidas',
  'liabilities.monthly_payment': 'Parcelas mensais das dívidas',
  goals: 'Objetivos financeiros',
};

function isKnown(value: MoneyValue): value is string | number {
  return value !== null && value !== undefined && value !== '';
}

function money(value: MoneyValue) {
  return isKnown(value) ? formatCurrency(value) : 'Não informado';
}

function ratio(value: MoneyValue) {
  return isKnown(value) ? formatPercent(value) : 'Não informado';
}

function months(value: MoneyValue) {
  return isKnown(value) ? `${Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} meses` : 'Não informado';
}

function qualityTone(quality: DataQuality): 'success' | 'warning' | 'danger' {
  if (quality === 'COMPLETE') return 'success';
  if (quality === 'INCONSISTENT' || quality === 'INSUFFICIENT') return 'danger';
  return 'warning';
}

function readableMissing(field: string) {
  if (missingLabels[field]) return missingLabels[field];
  if (field.includes('.recurring_income')) return 'Renda recorrente de um membro';
  if (field.includes('.expense_nature')) return 'Classificação fixa ou variável de uma despesa';
  if (field.includes('.current_value')) return 'Valor atual de um patrimônio';
  if (field.includes('.current_balance')) return 'Saldo atual de uma dívida';
  if (field.includes('.monthly_payment')) return 'Parcela mensal de uma dívida';
  if (field.includes('.current_amount')) return 'Valor já acumulado em um objetivo';
  return 'Uma informação financeira necessária ainda não foi informada';
}

function readableInconsistency(field: string) {
  if (field.includes('paid_with_balance')) return 'Uma dívida marcada como paga ainda possui saldo';
  if (field.startsWith('incomes.')) return 'Uma receita precisa ser revisada';
  if (field.startsWith('expenses.')) return 'Uma despesa precisa ser revisada';
  if (field.startsWith('liabilities.')) return 'Uma dívida precisa ser revisada';
  if (field.startsWith('assets.')) return 'Um item do patrimônio precisa ser revisado';
  if (field.startsWith('goals.')) return 'Um objetivo precisa ser revisado';
  if (field.startsWith('members.')) return 'O vínculo de um membro precisa ser revisado';
  return 'Uma informação financeira está inconsistente';
}

function readableStale(field: string) {
  if (field === 'incomes') return 'As receitas não são atualizadas há mais de 45 dias';
  if (field === 'expenses') return 'As despesas não são atualizadas há mais de 45 dias';
  if (field.startsWith('liabilities.')) return 'O saldo de uma dívida está desatualizado';
  if (field.startsWith('assets.')) return 'O valor de um item do patrimônio está desatualizado';
  if (field.startsWith('financial_profiles.')) return 'Os dados financeiros básicos estão desatualizados';
  return 'Uma informação financeira está desatualizada';
}

export function FinancialPage() {
  const households = useHouseholds();
  const defaultHousehold = useDefaultHousehold();
  const profile = useFinancialProfile();
  const [selectedHouseholdId, setSelectedHouseholdId] = useState<number | null>(null);
  const [selectedActionPlanId, setSelectedActionPlanId] = useState<number | null>(null);
  const [showIncomeForm, setShowIncomeForm] = useState(false);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [incomeSaved, setIncomeSaved] = useState(false);
  const [expenseSaved, setExpenseSaved] = useState(false);
  const [income, setIncome] = useState<{
    description: string;
    amount: string;
    income_type: string;
    received_at: string;
    is_recurring: boolean;
    ownership_scope: OwnershipScope;
  }>({ description: '', amount: '', income_type: 'salario', received_at: today(), is_recurring: true, ownership_scope: 'PERSONAL' });
  const [expense, setExpense] = useState<{
    description: string;
    amount: string;
    category: string;
    due_date: string;
    paid_at: string;
    is_paid: boolean;
    is_recurring: boolean;
    expense_nature: 'FIXED' | 'VARIABLE';
    ownership_scope: OwnershipScope;
  }>({
    description: '',
    amount: '',
    category: 'moradia',
    due_date: today(),
    paid_at: '',
    is_paid: false,
    is_recurring: true,
    expense_nature: 'FIXED',
    ownership_scope: 'PERSONAL',
  });

  useEffect(() => {
    if (selectedHouseholdId === null && defaultHousehold.data) {
      setSelectedHouseholdId(defaultHousehold.data.id);
    }
  }, [defaultHousehold.data, selectedHouseholdId]);

  const financialState = useCurrentFinancialState(selectedHouseholdId);
  const financialPolicy = useCurrentFinancialPolicy(selectedHouseholdId);
  const policyHistory = useFinancialPolicyHistory(selectedHouseholdId);
  const capitalAllocation = useCurrentCapitalAllocation(selectedHouseholdId);
  const allocationHistory = useCapitalAllocationHistory(selectedHouseholdId);
  const investmentOrchestration = useCurrentInvestmentOrchestration(selectedHouseholdId);
  const orchestrationHistory = useInvestmentOrchestrationHistory(selectedHouseholdId);
  const actionPlan = useCurrentActionPlan(selectedHouseholdId);
  const actionPlanHistory = useActionPlanHistory(selectedHouseholdId);
  const frozenActionPlan = useActionPlanDecision(selectedHouseholdId, selectedActionPlanId);
  const incomes = useHouseholdIncomes(selectedHouseholdId);
  const expenses = useHouseholdExpenses(selectedHouseholdId);
  const createIncome = useCreateHouseholdIncome(selectedHouseholdId);
  const createExpense = useCreateHouseholdExpense(selectedHouseholdId);
  const createSnapshot = useCreateFinancialStateSnapshot(selectedHouseholdId);
  const createPolicyDecision = useCreateFinancialPolicyDecision(selectedHouseholdId);
  const createAllocationDecision = useCreateCapitalAllocationDecision(selectedHouseholdId);
  const createOrchestrationDecision = useCreateInvestmentOrchestrationDecision(selectedHouseholdId);
  const createActionPlanDecision = useCreateActionPlanDecision(selectedHouseholdId);
  const missingProfile = (profile.error as ApiErrorShape | null)?.status === 404;
  const loadError = getActionError(
    households.error,
    defaultHousehold.error,
    financialState.error,
    incomes.error,
    expenses.error,
    !missingProfile ? profile.error : null,
  );
  const entryError = getActionError(createIncome.error, createExpense.error);
  const state = financialState.data;
  const metrics = state?.metrics;

  useEffect(() => {
    if (!incomeSaved && !expenseSaved) return;
    const timer = window.setTimeout(() => {
      setIncomeSaved(false);
      setExpenseSaved(false);
    }, 3600);
    return () => window.clearTimeout(timer);
  }, [incomeSaved, expenseSaved]);

  useEffect(() => {
    setSelectedActionPlanId(null);
  }, [selectedHouseholdId]);

  async function submitIncome(event: FormEvent) {
    event.preventDefault();
    if (createIncome.isPending) return;
    await createIncome.mutateAsync({ ...income, amount: Number(income.amount) });
    setIncome({ description: '', amount: '', income_type: 'salario', received_at: today(), is_recurring: true, ownership_scope: 'PERSONAL' });
    setShowIncomeForm(false);
    setIncomeSaved(true);
  }

  async function submitExpense(event: FormEvent) {
    event.preventDefault();
    if (createExpense.isPending) return;
    await createExpense.mutateAsync({ ...expense, amount: Number(expense.amount), paid_at: expense.paid_at || null });
    setExpense({
      description: '',
      amount: '',
      category: 'moradia',
      due_date: today(),
      paid_at: '',
      is_paid: false,
      is_recurring: true,
      expense_nature: 'FIXED',
      ownership_scope: 'PERSONAL',
    });
    setShowExpenseForm(false);
    setExpenseSaved(true);
  }

  function reload() {
    households.refetch();
    defaultHousehold.refetch();
    financialState.refetch();
    financialPolicy.refetch();
    policyHistory.refetch();
    capitalAllocation.refetch();
    allocationHistory.refetch();
    investmentOrchestration.refetch();
    orchestrationHistory.refetch();
    actionPlan.refetch();
    actionPlanHistory.refetch();
    incomes.refetch();
    expenses.refetch();
    profile.refetch();
  }

  return (
    <section className="vn-page">
      <SectionHeader
        eyebrow="Financial Autopilot · fase 5"
        title="Minha situação financeira"
        description="Uma leitura objetiva da sua situação e da ordem de prioridades agora — com transparência sobre o que ainda falta informar."
        action={state ? <Button variant="secondary" onClick={() => createSnapshot.mutate()} disabled={createSnapshot.isPending}>{createSnapshot.isPending ? 'Salvando...' : 'Salvar retrato'}</Button> : undefined}
      />

      {loadError && <Card><ErrorState title="Não foi possível carregar sua situação" description={loadError.message} action={<Button variant="secondary" onClick={reload}>Tentar novamente</Button>} /></Card>}
      {entryError && <Card><ErrorState title="Não foi possível salvar o lançamento" description={entryError.message} /></Card>}
      {createSnapshot.error && (
        <Card>
          <ErrorState
            title="Não foi possível salvar o retrato"
            description={errorMessage(createSnapshot.error)}
            action={<Button variant="secondary" onClick={() => createSnapshot.mutate()} disabled={createSnapshot.isPending}>Tentar salvar novamente</Button>}
          />
        </Card>
      )}
      {createSnapshot.isSuccess && <Toast message="Retrato financeiro salvo no histórico." />}
      {createPolicyDecision.isSuccess && <Toast message="Decisão financeira salva no histórico." />}
      {createAllocationDecision.isSuccess && <Toast message="Plano de capital salvo no histórico." />}
      {createOrchestrationDecision.isSuccess && <Toast message="Estratégia de investimento salva no histórico." />}
      {createActionPlanDecision.isSuccess && <Toast message="Plano de ação salvo no histórico." />}
      {incomeSaved && <Toast message="Receita cadastrada com sucesso." />}
      {expenseSaved && <Toast message="Despesa cadastrada com sucesso." />}
      {missingProfile && <OnboardingCard onCompleted={reload} />}

      {(households.isLoading || defaultHousehold.isLoading || (selectedHouseholdId !== null && (financialState.isLoading || incomes.isLoading || expenses.isLoading))) && <Card><LoadingState label="Organizando sua situação financeira..." /></Card>}

      {households.data && households.data.length > 1 && (
        <Card title="Visão financeira" description="Alterne entre sua situação pessoal e os households dos quais você participa.">
          <label className="vn-field">
            <span>Household</span>
            <select className="vn-input" value={selectedHouseholdId ?? ''} onChange={(event) => setSelectedHouseholdId(Number(event.target.value))}>
              {households.data.map((household) => <option key={household.id} value={household.id}>{household.name}</option>)}
            </select>
          </label>
        </Card>
      )}

      {selectedHouseholdId !== null && (
        <div className="vn-grid vn-grid--two">
          <Card
            title="Receitas"
            description="Entradas pessoais ou compartilhadas usadas pelo Financial State."
            action={<Button variant="secondary" onClick={() => setShowIncomeForm((value) => !value)}>{showIncomeForm ? 'Fechar' : 'Nova receita'}</Button>}
          >
            {!showIncomeForm && incomes.data?.length === 0 && (
              <EmptyState
                title="Nenhuma receita cadastrada"
                description="Cadastre uma receita ou informe explicitamente zero para registrar uma ausência real de renda."
                action={<Button onClick={() => setShowIncomeForm(true)}>Cadastrar primeira receita</Button>}
              />
            )}
            {showIncomeForm && (
              <form className="vn-form vn-compact-form" onSubmit={submitIncome}>
                <Input label="Descrição" placeholder="Ex.: Salário CLT" value={income.description} onChange={(event) => setIncome({ ...income, description: event.target.value })} required />
                <MoneyInput label="Valor" value={income.amount} onChange={(event) => setIncome({ ...income, amount: event.target.value })} required />
                <SelectField label="Tipo" value={income.income_type} onChange={(event) => setIncome({ ...income, income_type: event.target.value })} options={incomeTypeOptions} />
                <SelectField label="Pertence a" value={income.ownership_scope} onChange={(event) => setIncome({ ...income, ownership_scope: event.target.value as OwnershipScope })} options={ownershipOptions} />
                <FormField label="Data de recebimento"><input className="vn-input" type="date" value={income.received_at} onChange={(event) => setIncome({ ...income, received_at: event.target.value })} required /></FormField>
                <ToggleField label="Receita recorrente" checked={income.is_recurring} onChange={(event) => setIncome({ ...income, is_recurring: event.target.checked })} />
                <SubmitButton loading={createIncome.isPending}>Salvar receita</SubmitButton>
              </form>
            )}
            {incomes.isLoading ? <LoadingState label="Carregando receitas..." /> : (
              <div className="vn-list vn-section-gap">
                {incomes.data?.map((item) => (
                  <div key={item.id}>
                    <strong>
                      {item.description}{' '}
                      <Badge>{item.is_recurring ? 'recorrente' : 'pontual'}</Badge>
                      <Badge>{item.ownership_scope === 'HOUSEHOLD' ? 'household' : 'pessoal'}</Badge>
                    </strong>
                    <span>{money(item.amount)} · {item.income_type} · {item.received_at}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card
            title="Despesas"
            description="Saídas pessoais ou compartilhadas, classificadas como fixas ou variáveis."
            action={<Button variant="secondary" onClick={() => setShowExpenseForm((value) => !value)}>{showExpenseForm ? 'Fechar' : 'Nova despesa'}</Button>}
          >
            {!showExpenseForm && expenses.data?.length === 0 && (
              <EmptyState
                title="Nenhuma despesa cadastrada"
                description="Cadastre uma despesa ou informe explicitamente zero para registrar uma ausência real de gastos."
                action={<Button onClick={() => setShowExpenseForm(true)}>Cadastrar primeira despesa</Button>}
              />
            )}
            {showExpenseForm && (
              <form className="vn-form vn-compact-form" onSubmit={submitExpense}>
                <Input label="Descrição" placeholder="Ex.: Aluguel" value={expense.description} onChange={(event) => setExpense({ ...expense, description: event.target.value })} required />
                <MoneyInput label="Valor" value={expense.amount} onChange={(event) => setExpense({ ...expense, amount: event.target.value })} required />
                <SelectField label="Categoria" value={expense.category} onChange={(event) => setExpense({ ...expense, category: event.target.value })} options={categoryOptions} />
                <SelectField label="Natureza" value={expense.expense_nature} onChange={(event) => setExpense({ ...expense, expense_nature: event.target.value as 'FIXED' | 'VARIABLE' })} options={expenseNatureOptions} />
                <SelectField label="Pertence a" value={expense.ownership_scope} onChange={(event) => setExpense({ ...expense, ownership_scope: event.target.value as OwnershipScope })} options={ownershipOptions} />
                <FormField label="Vencimento"><input className="vn-input" type="date" value={expense.due_date} onChange={(event) => setExpense({ ...expense, due_date: event.target.value })} required /></FormField>
                <FormField label="Pagamento"><input className="vn-input" type="date" value={expense.paid_at} onChange={(event) => setExpense({ ...expense, paid_at: event.target.value })} /></FormField>
                <ToggleField label="Despesa paga" checked={expense.is_paid} onChange={(event) => setExpense({ ...expense, is_paid: event.target.checked })} />
                <ToggleField label="Despesa recorrente" checked={expense.is_recurring} onChange={(event) => setExpense({ ...expense, is_recurring: event.target.checked })} />
                <SubmitButton loading={createExpense.isPending}>Salvar despesa</SubmitButton>
              </form>
            )}
            {expenses.isLoading ? <LoadingState label="Carregando despesas..." /> : (
              <div className="vn-list vn-section-gap">
                {expenses.data?.map((item) => (
                  <div key={item.id}>
                    <strong>
                      {item.description}{' '}
                      <Badge tone={item.is_paid ? 'success' : 'warning'}>{item.is_paid ? 'paga' : 'pendente'}</Badge>
                      <Badge>{item.expense_nature === 'FIXED' ? 'fixa' : item.expense_nature === 'VARIABLE' ? 'variável' : 'não classificada'}</Badge>
                      <Badge>{item.ownership_scope === 'HOUSEHOLD' ? 'household' : 'pessoal'}</Badge>
                    </strong>
                    <span>{money(item.amount)} · {item.category} · vence em {item.due_date}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {state && metrics && (
        <>
          <FinancialPolicyCard
            policy={financialPolicy.data}
            history={policyHistory.data}
            isLoading={financialPolicy.isLoading}
            isHistoryLoading={policyHistory.isLoading}
            isFreezing={createPolicyDecision.isPending}
            errorMessage={financialPolicy.error ? errorMessage(financialPolicy.error) : undefined}
            historyErrorMessage={policyHistory.error ? errorMessage(policyHistory.error) : undefined}
            freezeErrorMessage={createPolicyDecision.error ? errorMessage(createPolicyDecision.error) : undefined}
            onRetry={() => financialPolicy.refetch()}
            onRetryHistory={() => policyHistory.refetch()}
            onFreeze={() => createPolicyDecision.mutate()}
          />

          <CapitalAllocationCard
            allocation={capitalAllocation.data}
            history={allocationHistory.data}
            isLoading={capitalAllocation.isLoading}
            isHistoryLoading={allocationHistory.isLoading}
            isFreezing={createAllocationDecision.isPending}
            errorMessage={capitalAllocation.error ? errorMessage(capitalAllocation.error) : undefined}
            historyErrorMessage={allocationHistory.error ? errorMessage(allocationHistory.error) : undefined}
            freezeErrorMessage={createAllocationDecision.error ? errorMessage(createAllocationDecision.error) : undefined}
            onRetry={() => capitalAllocation.refetch()}
            onRetryHistory={() => allocationHistory.refetch()}
            onFreeze={() => createAllocationDecision.mutate()}
          />

          <InvestmentOrchestrationCard
            orchestration={investmentOrchestration.data}
            history={orchestrationHistory.data}
            isLoading={investmentOrchestration.isLoading}
            isHistoryLoading={orchestrationHistory.isLoading}
            isFreezing={createOrchestrationDecision.isPending}
            errorMessage={investmentOrchestration.error ? errorMessage(investmentOrchestration.error) : undefined}
            historyErrorMessage={orchestrationHistory.error ? errorMessage(orchestrationHistory.error) : undefined}
            freezeErrorMessage={createOrchestrationDecision.error ? errorMessage(createOrchestrationDecision.error) : undefined}
            onRetry={() => investmentOrchestration.refetch()}
            onRetryHistory={() => orchestrationHistory.refetch()}
            onFreeze={() => createOrchestrationDecision.mutate()}
          />

          <ActionPlanCard
            plan={selectedActionPlanId === null ? actionPlan.data : frozenActionPlan.data}
            history={actionPlanHistory.data}
            isLoading={selectedActionPlanId === null ? actionPlan.isLoading : frozenActionPlan.isLoading}
            isHistoryLoading={actionPlanHistory.isLoading}
            isFreezing={createActionPlanDecision.isPending}
            isHistorical={selectedActionPlanId !== null}
            errorMessage={
              selectedActionPlanId === null
                ? (actionPlan.error ? errorMessage(actionPlan.error) : undefined)
                : (frozenActionPlan.error ? errorMessage(frozenActionPlan.error) : undefined)
            }
            historyErrorMessage={actionPlanHistory.error ? errorMessage(actionPlanHistory.error) : undefined}
            freezeErrorMessage={createActionPlanDecision.error ? errorMessage(createActionPlanDecision.error) : undefined}
            onRetry={() => (
              selectedActionPlanId === null ? actionPlan.refetch() : frozenActionPlan.refetch()
            )}
            onRetryHistory={() => actionPlanHistory.refetch()}
            onFreeze={() => createActionPlanDecision.mutate()}
            onSelectHistory={setSelectedActionPlanId}
            onShowCurrent={() => setSelectedActionPlanId(null)}
          />

          <Card
            title="Qualidade dos dados"
            description="A confiança mede completude e atualidade das informações; não é uma previsão de mercado."
            action={<Badge tone={qualityTone(state.data_quality)}>{qualityLabels[state.data_quality]} · {state.confidence}%</Badge>}
          >
            <p>Avaliação em {new Date(state.evaluated_at).toLocaleString('pt-BR')} com o engine <strong>{state.engine_version}</strong>.</p>
          </Card>

          <div className="vn-metrics vn-metrics--refined">
            <MetricCard label="Renda recorrente mensal" value={money(metrics.recurring_monthly_income)} helper="Valor conhecido no mês avaliado." />
            <MetricCard label="Despesas totais" value={money(metrics.total_expenses)} helper={`Fixas: ${money(metrics.fixed_expenses)} · Variáveis: ${money(metrics.variable_expenses)}`} />
            <MetricCard label="Fluxo de caixa" value={money(metrics.cash_flow)} helper="Renda total menos despesas totais." tone={isKnown(metrics.cash_flow) && Number(metrics.cash_flow) < 0 ? 'warning' : 'success'} />
            <MetricCard label="Renda disponível" value={money(metrics.disposable_income)} helper="Renda recorrente menos despesas." />
            <MetricCard label="Capacidade de poupança" value={money(metrics.savings_capacity)} helper={`Taxa de poupança: ${ratio(metrics.savings_rate)}`} />
            <MetricCard label="Capacidade de investimento" value={money(metrics.investment_capacity)} helper="Após despesas e serviço conhecido das dívidas." />
            <MetricCard label="Reserva de emergência" value={money(metrics.emergency_reserve)} helper={`Cobertura: ${months(metrics.emergency_reserve_months)}`} />
            <MetricCard label="Patrimônio líquido" value={money(metrics.net_worth)} helper={`Ativos: ${money(metrics.total_assets)} · Dívidas: ${money(metrics.total_liabilities)}`} />
            <MetricCard label="Comprometimento com dívidas" value={ratio(metrics.debt_service_ratio)} helper={`Parcelas mensais: ${money(metrics.monthly_debt_service)}`} />
          </div>

          {(state.missing_fields.length > 0 || state.inconsistencies.length > 0 || state.stale_fields.length > 0) && (
            <div className="vn-grid vn-grid--two">
              <Card title="Informações que ainda faltam" description="Campos ausentes permanecem como não informados; o Vinance não os converte em zero.">
                {state.missing_fields.length === 0 ? <p>Nenhuma informação essencial ausente.</p> : <ul>{state.missing_fields.map((field) => <li key={field}>{readableMissing(field)}</li>)}</ul>}
              </Card>
              <Card title="Pontos de atenção" description="Inconsistências ou dados antigos reduzem a confiança desta leitura.">
                {state.inconsistencies.length === 0 && state.stale_fields.length === 0 ? <p>Nenhum ponto de atenção identificado.</p> : (
                  <ul>
                    {state.inconsistencies.map((item) => <li key={`inconsistent-${item}`}>{readableInconsistency(item)}</li>)}
                    {state.stale_fields.map((item) => <li key={`stale-${item}`}>{readableStale(item)}</li>)}
                  </ul>
                )}
              </Card>
            </div>
          )}

          <div className="vn-grid vn-grid--two">
            <Card title="Distribuição patrimonial" description="Somente valores de patrimônio efetivamente informados.">
              {!metrics.asset_distribution || Object.keys(metrics.asset_distribution).length === 0 ? (
                <EmptyState title="Patrimônio não informado" description="Cadastre seus ativos para visualizar a composição patrimonial." />
              ) : (
                <div className="vn-list">
                  {Object.entries(metrics.asset_distribution).map(([assetClass, allocation]) => (
                    <div key={assetClass}><strong>{assetClassLabels[assetClass] ?? 'Outra classe patrimonial'}</strong><span>{money(allocation.amount)} · {ratio(allocation.percentage)}</span></div>
                  ))}
                </div>
              )}
            </Card>
            <Card title="Objetivos" description="Funding gaps consideram apenas valores conhecidos; deadlines nunca são inventadas.">
              {state.goals.length === 0 ? (
                <EmptyState title="Objetivos não informados" description="Cadastre um objetivo para acompanhar o valor necessário e o que já foi acumulado." />
              ) : (
                <div className="vn-list">
                  {state.goals.map((goal) => (
                    <div key={goal.id}>
                      <strong>{goal.name} <Badge>{goal.ownership_scope === 'HOUSEHOLD' ? 'household' : 'pessoal'}</Badge></strong>
                      <span>Meta: {money(goal.target_amount)} · Atual: {money(goal.current_amount)} · Falta: {money(goal.funding_gap)} · Prazo: {goal.deadline ?? 'Não informado'}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {state.member_views.length > 1 && (
            <Card title="Visão por membro" description="Renda, gastos e patrimônio pessoais permanecem separados da visão consolidada.">
              <div className="vn-grid vn-grid--two">
                {state.member_views.map((member) => (
                  <div key={member.user_id}>
                    <strong>{member.full_name || `Membro ${member.user_id}`}</strong>
                    <p>Renda recorrente: {money(member.metrics.recurring_monthly_income)}</p>
                    <p>Despesas: {money(member.metrics.total_expenses)}</p>
                    <p>Patrimônio líquido: {money(member.metrics.net_worth)}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </section>
  );
}
