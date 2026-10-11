import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Card, EmptyState, ErrorState, Input, LoadingState, Modal, MoneyInput, SectionHeader, SelectField, Toast, ToggleField } from '../components';
import { useCurrentUser, useSessionToken } from '../features/auth/hooks/useAuth';
import { useFinancialProfile, useScopedUpsertProfile } from '../features/financial/hooks/useFinancial';
import {
  useCreateFinancialResource,
  useDeleteFinancialResource,
  useFinancialResourceList,
  useUpdateFinancialResource,
  type FinancialResource,
  type FinancialResourceItem,
} from '../features/financial-state/hooks/useFinancialResources';
import type { OwnershipScope } from '../features/financial-state/types/financialState.types';
import { useHouseholdDefault, useHouseholdList, useHouseholdMembers } from '../features/household/hooks/useHousehold';
import { formatCurrency } from '../utils/formatters';
import { localDateInputValue } from '../utils/localDate';
import type { ApiErrorShape } from '../services/api';

type EditorMode = 'create' | 'edit';
type Draft = {
  scope: OwnershipScope;
  description: string;
  amount: string;
  kind: string;
  date: string;
  recurring: boolean;
  category: string;
  paidAt: string;
  paid: boolean;
  nature: 'FIXED' | 'VARIABLE';
  monthlyPayment: string;
  interestRate: string;
  secondaryDate: string;
  assetClass: 'CASH' | 'EMERGENCY_RESERVE' | 'FIXED_INCOME' | 'INVESTMENTS' | 'REAL_ESTATE' | 'VEHICLES' | 'OTHER';
  currentAmount: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  currency: string;
  assetCatalogId: number | null;
  liabilityStatus: 'ACTIVE' | 'PAID' | 'DEFAULTED' | 'CANCELLED';
  assetStatus: 'ACTIVE' | 'DISPOSED';
  goalStatus: 'ACTIVE' | 'PAUSED' | 'COMPLETED' | 'CANCELLED';
};

type Editor = {
  resource: FinancialResource;
  mode: EditorMode;
  recordId: number | null;
  householdId: number;
  sessionToken: string | null;
  originalScope: OwnershipScope | null;
  ownerUserId: number | null;
  dirty: boolean;
  draft: Draft;
};

const labels: Record<FinancialResource, { singular: string; plural: string; description: string }> = {
  incomes: { singular: 'receita', plural: 'Receitas', description: 'Entradas recorrentes ou pontuais.' },
  expenses: { singular: 'despesa', plural: 'Despesas', description: 'Gastos fixos e variáveis.' },
  debts: { singular: 'dívida', plural: 'Dívidas', description: 'Obrigações reais, sem inventar taxa ou vencimento.' },
  assets: { singular: 'patrimônio', plural: 'Patrimônio', description: 'Bens e saldos que pertencem a você ou à casa.' },
  goals: { singular: 'objetivo', plural: 'Objetivos', description: 'Metas financeiras com prazo opcional.' },
};

const resources: FinancialResource[] = ['incomes', 'expenses', 'debts', 'assets', 'goals'];

function emptyDraft(): Draft {
  return {
    scope: 'PERSONAL',
    description: '',
    amount: '',
    kind: '',
    date: localDateInputValue(),
    recurring: true,
    category: '',
    paidAt: '',
    paid: false,
    nature: 'FIXED',
    monthlyPayment: '',
    interestRate: '',
    secondaryDate: '',
    assetClass: 'CASH',
    currentAmount: '',
    priority: 'MEDIUM',
    currency: 'BRL',
    assetCatalogId: null,
    liabilityStatus: 'ACTIVE',
    assetStatus: 'ACTIVE',
    goalStatus: 'ACTIVE',
  };
}

function optionalMoney(value: string) {
  return value.trim() === '' ? null : Number(value);
}

function optionalDate(value: string) {
  return value.trim() === '' ? null : value;
}

function money(value: unknown) {
  return value === null || value === undefined || value === '' ? 'Não informado' : formatCurrency(value as string | number);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Não foi possível concluir esta ação.';
}

function itemScope(item: FinancialResourceItem) {
  return item.ownership_scope;
}

function itemTitle(resource: FinancialResource, item: FinancialResourceItem) {
  if (resource === 'incomes' || resource === 'expenses') return (item as { description: string }).description;
  return (item as { name: string | null }).name || 'Ativo vinculado ao catálogo';
}

function itemAmount(resource: FinancialResource, item: FinancialResourceItem) {
  if (resource === 'incomes' || resource === 'expenses') return (item as { amount: unknown }).amount;
  if (resource === 'debts') return (item as { current_balance: unknown }).current_balance;
  if (resource === 'assets') return (item as { current_value: unknown }).current_value;
  return (item as { target_amount: unknown }).target_amount;
}

function draftFromItem(resource: FinancialResource, item: FinancialResourceItem): Draft {
  const draft = emptyDraft();
  draft.scope = item.ownership_scope;
  if (resource === 'incomes') {
    const value = item as any;
    return { ...draft, description: value.description, amount: String(value.amount), kind: value.income_type, date: value.received_at, recurring: value.is_recurring };
  }
  if (resource === 'expenses') {
    const value = item as any;
    return { ...draft, description: value.description, amount: String(value.amount), category: value.category, date: value.due_date, paidAt: value.paid_at ?? '', paid: value.is_paid, recurring: value.is_recurring, nature: value.expense_nature ?? 'VARIABLE' };
  }
  if (resource === 'debts') {
    const value = item as any;
    return { ...draft, description: value.name, kind: value.liability_type, amount: value.current_balance == null ? '' : String(value.current_balance), monthlyPayment: value.monthly_payment == null ? '' : String(value.monthly_payment), interestRate: value.annual_interest_rate_pct == null ? '' : String(value.annual_interest_rate_pct), date: value.due_date ?? '', secondaryDate: value.balance_as_of ?? '', currency: value.currency, liabilityStatus: value.status };
  }
  if (resource === 'assets') {
    const value = item as any;
    return { ...draft, description: value.name ?? '', assetClass: value.asset_class, amount: value.current_value == null ? '' : String(value.current_value), date: value.value_as_of ?? '', currency: value.currency, assetCatalogId: value.asset_catalog_id, assetStatus: value.status };
  }
  const value = item as any;
  return { ...draft, description: value.name, amount: String(value.target_amount), currentAmount: value.current_amount == null ? '' : String(value.current_amount), date: value.deadline ?? '', priority: value.priority, currency: value.currency, goalStatus: value.status };
}

function payloadFromDraft(resource: FinancialResource, draft: Draft) {
  if (resource === 'incomes') return {
    ownership_scope: draft.scope,
    description: draft.description.trim(),
    amount: Number(draft.amount),
    income_type: draft.kind.trim() || 'outros',
    received_at: draft.date,
    is_recurring: draft.recurring,
  };
  if (resource === 'expenses') return {
    ownership_scope: draft.scope,
    description: draft.description.trim(),
    amount: Number(draft.amount),
    category: draft.category.trim() || 'outros',
    due_date: draft.date,
    paid_at: optionalDate(draft.paidAt),
    is_paid: draft.paid,
    is_recurring: draft.recurring,
    expense_nature: draft.nature,
  };
  if (resource === 'debts') return {
    ownership_scope: draft.scope,
    name: draft.description.trim(),
    liability_type: draft.kind.trim() || 'other',
    current_balance: optionalMoney(draft.amount),
    monthly_payment: optionalMoney(draft.monthlyPayment),
    annual_interest_rate_pct: optionalMoney(draft.interestRate),
    due_date: optionalDate(draft.date),
    balance_as_of: optionalDate(draft.secondaryDate),
    currency: draft.currency.trim().toUpperCase(),
    status: draft.liabilityStatus,
  };
  if (resource === 'assets') return {
    ownership_scope: draft.scope,
    asset_class: draft.assetClass,
    asset_catalog_id: draft.assetCatalogId,
    name: draft.description.trim() || null,
    current_value: optionalMoney(draft.amount),
    value_as_of: optionalDate(draft.date),
    currency: draft.currency.trim().toUpperCase(),
    status: draft.assetStatus,
  };
  return {
    ownership_scope: draft.scope,
    name: draft.description.trim(),
    target_amount: Number(draft.amount),
    current_amount: optionalMoney(draft.currentAmount),
    deadline: optionalDate(draft.date),
    priority: draft.priority,
    currency: draft.currency.trim().toUpperCase(),
    status: draft.goalStatus,
  };
}

function emptyProfileDraft() {
  return {
    monthlySalary: '',
    emergencyReserve: '',
    hasDebtDefault: false,
    riskProfile: 'moderate' as 'conservative' | 'moderate' | 'aggressive',
    investmentHorizonMonths: '',
  };
}

export function FinancialDataPage() {
  const sessionToken = useSessionToken();
  const currentUser = useCurrentUser();
  const households = useHouseholdList();
  const defaultHousehold = useHouseholdDefault();
  const profile = useFinancialProfile();
  const saveProfile = useScopedUpsertProfile();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [pendingSwitchId, setPendingSwitchId] = useState<number | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileDirty, setProfileDirty] = useState(false);
  const [profileDraft, setProfileDraft] = useState(emptyProfileDraft);
  const [notice, setNotice] = useState<string | null>(null);
  const previousSession = useRef(sessionToken);

  const incomes = useFinancialResourceList('incomes', selectedId);
  const expenses = useFinancialResourceList('expenses', selectedId);
  const debts = useFinancialResourceList('debts', selectedId);
  const assets = useFinancialResourceList('assets', selectedId);
  const goals = useFinancialResourceList('goals', selectedId);
  const members = useHouseholdMembers(selectedId);
  const queryByResource = { incomes, expenses, debts, assets, goals };
  const createResource = useCreateFinancialResource();
  const updateResource = useUpdateFinancialResource();
  const deleteResource = useDeleteFinancialResource();
  const selectedHousehold = households.data?.find((item) => item.id === selectedId) ?? null;
  const currentMembership = members.data?.find((item) => item.user_id === currentUser.data?.id);
  const pendingMutation = createResource.isPending || updateResource.isPending || deleteResource.isPending || saveProfile.isPending;
  const missingProfile = (profile.error as ApiErrorShape | null)?.status === 404;
  const loadError = households.error || defaultHousehold.error || members.error || (!missingProfile && profile.error) || resources.map((resource) => queryByResource[resource].error).find(Boolean);
  const actionError = createResource.error || updateResource.error || deleteResource.error || saveProfile.error;

  useEffect(() => {
    if (selectedId === null && defaultHousehold.data) setSelectedId(defaultHousehold.data.id);
  }, [defaultHousehold.data, selectedId]);

  useEffect(() => {
    if (!households.data?.length) return;
    if (selectedId !== null && households.data.some((item) => item.id === selectedId)) return;
    setSelectedId(defaultHousehold.data?.id ?? households.data[0].id);
  }, [defaultHousehold.data?.id, households.data, selectedId]);

  useEffect(() => {
    if (!profile.data || profileDirty) return;
    setProfileDraft({
      monthlySalary: String(profile.data.monthly_salary),
      emergencyReserve: String(profile.data.emergency_reserve),
      hasDebtDefault: profile.data.has_debt_default,
      riskProfile: profile.data.risk_profile,
      investmentHorizonMonths: profile.data.investment_horizon_months == null
        ? ''
        : String(profile.data.investment_horizon_months),
    });
  }, [profile.data, profileDirty]);

  useEffect(() => {
    if (previousSession.current === sessionToken) return;
    previousSession.current = sessionToken;
    setSelectedId(null);
    setPendingSwitchId(null);
    setEditor(null);
    setProfileEditing(false);
    setProfileDirty(false);
    setProfileDraft(emptyProfileDraft());
    setNotice(null);
  }, [sessionToken]);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 3500);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  const groupedCounts = useMemo(() => Object.fromEntries(resources.map((resource) => [resource, (queryByResource[resource].data ?? []).length])), [assets.data, debts.data, expenses.data, goals.data, incomes.data]);

  function requestSwitch(nextId: number) {
    if (nextId === selectedId || pendingMutation) return;
    if (editor?.dirty || profileDirty) {
      setPendingSwitchId(nextId);
      return;
    }
    setEditor(null);
    setProfileEditing(false);
    setSelectedId(nextId);
  }

  function discardAndSwitch() {
    if (pendingSwitchId === null) return;
    setEditor(null);
    setProfileEditing(false);
    setProfileDirty(false);
    setSelectedId(pendingSwitchId);
    setPendingSwitchId(null);
  }

  function openCreate(resource: FinancialResource) {
    if (selectedId === null) return;
    const draft = emptyDraft();
    if (resource === 'debts' || resource === 'assets' || resource === 'goals') draft.date = '';
    setEditor({ resource, mode: 'create', recordId: null, householdId: selectedId, sessionToken, originalScope: null, ownerUserId: currentUser.data?.id ?? null, dirty: false, draft });
  }

  function openEdit(resource: FinancialResource, item: FinancialResourceItem) {
    if (selectedId === null) return;
    setEditor({ resource, mode: 'edit', recordId: item.id, householdId: selectedId, sessionToken, originalScope: item.ownership_scope, ownerUserId: item.user_id, dirty: false, draft: draftFromItem(resource, item) });
  }

  function changeDraft(values: Partial<Draft>) {
    setEditor((current) => current ? { ...current, dirty: true, draft: { ...current.draft, ...values } } : null);
  }

  async function submitEditor(event: FormEvent) {
    event.preventDefault();
    if (!editor || pendingMutation) return;
    if (editor.householdId !== selectedId || editor.sessionToken !== sessionToken) {
      throw new Error('O contexto mudou. Feche e abra o formulário novamente.');
    }
    if (editor.mode === 'edit' && editor.originalScope === 'PERSONAL' && editor.draft.scope === 'HOUSEHOLD') {
      if (!window.confirm(`Compartilhar esta ${labels[editor.resource].singular}? Os membros ativos de ${selectedHousehold?.name ?? 'este household'} poderão visualizá-la.`)) return;
    }
    const payload = payloadFromDraft(editor.resource, editor.draft);
    if (editor.mode === 'create') {
      await createResource.mutateAsync({ householdId: editor.householdId, sessionToken: editor.sessionToken, resource: editor.resource, payload });
    } else {
      if (editor.ownerUserId !== currentUser.data?.id) delete (payload as { ownership_scope?: OwnershipScope }).ownership_scope;
      await updateResource.mutateAsync({ householdId: editor.householdId, sessionToken: editor.sessionToken, resource: editor.resource, recordId: editor.recordId as number, payload });
    }
    setNotice(`${labels[editor.resource].singular[0].toUpperCase()}${labels[editor.resource].singular.slice(1)} salva com sucesso.`);
    setEditor(null);
  }

  async function remove(resource: FinancialResource, item: FinancialResourceItem) {
    if (selectedId === null || !window.confirm(`Excluir esta ${labels[resource].singular}? O Autopilot será reavaliado quando aplicável.`)) return;
    await deleteResource.mutateAsync({ householdId: selectedId, sessionToken, resource, recordId: item.id });
    setNotice(`${labels[resource].singular[0].toUpperCase()}${labels[resource].singular.slice(1)} excluída.`);
  }

  async function submitProfile(event: FormEvent) {
    event.preventDefault();
    await saveProfile.mutateAsync({
      sessionToken,
      payload: {
        monthly_salary: Number(profileDraft.monthlySalary),
        emergency_reserve: Number(profileDraft.emergencyReserve),
        has_debt_default: profileDraft.hasDebtDefault,
        risk_profile: profileDraft.riskProfile,
        investment_horizon_months: profileDraft.investmentHorizonMonths.trim() === ''
          ? null
          : Number(profileDraft.investmentHorizonMonths),
      },
    });
    setProfileDirty(false);
    setProfileEditing(false);
    setNotice('Perfil financeiro atualizado.');
  }

  if (households.isLoading || defaultHousehold.isLoading || currentUser.isLoading) return <LoadingState label="Carregando seus dados financeiros..." />;

  return (
    <section className="vn-page">
      <SectionHeader eyebrow="Dados financeiros" title="Gerenciar minha vida financeira" description="Cadastre apenas o que conhece. Campo vazio continua desconhecido — nunca vira zero automaticamente." />
      {loadError && <Card><ErrorState title="Não foi possível carregar seus dados" description={errorMessage(loadError)} /></Card>}
      {actionError && <Card><ErrorState title="A alteração não foi salva" description={errorMessage(actionError)} /></Card>}
      {notice && <Toast message={notice} />}

      <Card title="Contexto" description="Dados pessoais são visíveis só para você; dados compartilhados aparecem aos membros ativos.">
        <SelectField
          label="Household"
          value={selectedId ?? ''}
          disabled={pendingMutation}
          onChange={(event) => requestSwitch(Number(event.target.value))}
          options={(households.data ?? []).map((item) => ({ value: String(item.id), label: `${item.name} · ${item.household_type === 'PERSONAL' ? 'Pessoal' : 'Compartilhado'}` }))}
        />
      </Card>

      <div className="vn-grid vn-grid--two">
        {resources.map((resource) => {
          const query = queryByResource[resource];
          const items = (query.data ?? []) as FinancialResourceItem[];
          return (
            <Card key={resource} title={labels[resource].plural} description={`${labels[resource].description} ${groupedCounts[resource]} cadastrado(s).`} action={<Button onClick={() => openCreate(resource)}>Adicionar</Button>}>
              {query.isLoading ? <LoadingState label={`Carregando ${labels[resource].plural.toLowerCase()}...`} /> : items.length === 0 ? (
                <EmptyState title={`Nenhuma ${labels[resource].singular} cadastrada`} description="Você pode adicionar agora ou voltar depois se ainda não souber a informação." action={<Button variant="secondary" onClick={() => openCreate(resource)}>Adicionar {labels[resource].singular}</Button>} />
              ) : (
                <div className="vn-list">
                  {items.map((item) => {
                    const canMutate = item.user_id === currentUser.data?.id
                      || (item.ownership_scope === 'HOUSEHOLD' && currentMembership?.role === 'OWNER');
                    return (
                    <div key={item.id}>
                      <div>
                        <strong>{itemTitle(resource, item)}</strong>
                        <p>{money(itemAmount(resource, item))} · {itemScope(item) === 'PERSONAL' ? 'Só eu' : `Compartilhado com ${selectedHousehold?.name ?? 'household'}`}</p>
                      </div>
                      <div className="vn-inline-actions">
                        <Badge tone={itemScope(item) === 'PERSONAL' ? 'warning' : 'success'}>{itemScope(item) === 'PERSONAL' ? 'Pessoal' : 'Compartilhado'}</Badge>
                        {canMutate && <Button variant="secondary" onClick={() => openEdit(resource, item)}>Editar</Button>}
                        {canMutate && <Button variant="ghost" disabled={pendingMutation} onClick={() => remove(resource, item)}>Excluir</Button>}
                      </div>
                    </div>
                    );
                  })}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <Card title="Meu perfil financeiro" description="Este perfil é pessoal e não é o mesmo que seu perfil de investidor." action={<Button variant="secondary" onClick={() => setProfileEditing((value) => !value)}>{profileEditing ? 'Fechar' : profile.data ? 'Editar perfil' : 'Criar perfil'}</Button>}>
        {!profileEditing && profile.data && (
          <div className="vn-grid vn-grid--three">
            <div><small>Renda mensal declarada</small><strong>{formatCurrency(profile.data.monthly_salary)}</strong></div>
            <div><small>Reserva declarada</small><strong>{formatCurrency(profile.data.emergency_reserve)}</strong></div>
            <div><small>Postura de risco</small><strong>{profile.data.risk_profile}</strong></div>
            <div><small>Horizonte de investimento</small><strong>{profile.data.investment_horizon_months == null ? 'Não informado' : `${profile.data.investment_horizon_months} meses`}</strong></div>
          </div>
        )}
        {!profileEditing && missingProfile && <EmptyState title="Perfil ainda não preenchido" description="Informe o básico para melhorar a leitura financeira. Você poderá editar depois." />}
        {profileEditing && (
          <form className="vn-form" onSubmit={submitProfile}>
            <MoneyInput label="Renda mensal" value={profileDraft.monthlySalary} min="0.01" required onChange={(event) => { setProfileDraft((current) => ({ ...current, monthlySalary: event.target.value })); setProfileDirty(true); }} />
            <MoneyInput label="Reserva de emergência" value={profileDraft.emergencyReserve} required onChange={(event) => { setProfileDraft((current) => ({ ...current, emergencyReserve: event.target.value })); setProfileDirty(true); }} />
            <SelectField label="Perfil financeiro de risco" value={profileDraft.riskProfile} onChange={(event) => { setProfileDraft((current) => ({ ...current, riskProfile: event.target.value as any })); setProfileDirty(true); }} options={[{ value: 'conservative', label: 'Conservador' }, { value: 'moderate', label: 'Moderado' }, { value: 'aggressive', label: 'Agressivo' }]} />
            <Input label="Horizonte de investimento (meses, opcional)" type="number" min="1" max="1200" value={profileDraft.investmentHorizonMonths} onChange={(event) => { setProfileDraft((current) => ({ ...current, investmentHorizonMonths: event.target.value })); setProfileDirty(true); }} helper="Prazo esperado para o capital de investimento. Não é o prazo de um objetivo específico." />
            <ToggleField label="Possui inadimplência declarada" checked={profileDraft.hasDebtDefault} onChange={(event) => { setProfileDraft((current) => ({ ...current, hasDebtDefault: event.target.checked })); setProfileDirty(true); }} />
            <Button type="submit" disabled={saveProfile.isPending}>{saveProfile.isPending ? 'Salvando...' : 'Salvar perfil'}</Button>
          </form>
        )}
      </Card>

      <Modal open={editor !== null} title={editor ? `${editor.mode === 'create' ? 'Adicionar' : 'Editar'} ${labels[editor.resource].singular}` : 'Dados financeiros'} onClose={() => { if (!editor?.dirty || window.confirm('Descartar alterações não salvas?')) setEditor(null); }}>
        {editor && (
          <form className="vn-form" onSubmit={submitEditor}>
            <SelectField label="Quem pode ver este dado?" value={editor.draft.scope} disabled={editor.mode === 'edit' && editor.ownerUserId !== currentUser.data?.id} onChange={(event) => changeDraft({ scope: event.target.value as OwnershipScope })} options={[{ value: 'PERSONAL', label: 'Só eu' }, { value: 'HOUSEHOLD', label: `Compartilhado com ${selectedHousehold?.name ?? 'household'}` }]} helper={editor.mode === 'edit' && editor.ownerUserId !== currentUser.data?.id ? 'Somente quem criou o registro pode alterar seu compartilhamento.' : 'Novos registros começam como pessoais. Compartilhar exige sua escolha explícita.'} />
            <Input label={editor.resource === 'incomes' || editor.resource === 'expenses' ? 'Descrição' : 'Nome'} value={editor.draft.description} onChange={(event) => changeDraft({ description: event.target.value })} required={editor.resource !== 'assets' || editor.draft.assetCatalogId === null} />
            {editor.resource === 'incomes' && <>
              <MoneyInput label="Valor" value={editor.draft.amount} onChange={(event) => changeDraft({ amount: event.target.value })} required />
              <Input label="Tipo de renda" value={editor.draft.kind} onChange={(event) => changeDraft({ kind: event.target.value })} placeholder="salário, freelance..." required />
              <Input label="Data de recebimento" type="date" value={editor.draft.date} onChange={(event) => changeDraft({ date: event.target.value })} required />
              <ToggleField label="Receita recorrente" checked={editor.draft.recurring} onChange={(event) => changeDraft({ recurring: event.target.checked })} />
            </>}
            {editor.resource === 'expenses' && <>
              <MoneyInput label="Valor" value={editor.draft.amount} onChange={(event) => changeDraft({ amount: event.target.value })} required />
              <Input label="Categoria" value={editor.draft.category} onChange={(event) => changeDraft({ category: event.target.value })} required />
              <Input label="Vencimento" type="date" value={editor.draft.date} onChange={(event) => changeDraft({ date: event.target.value })} required />
              <Input label="Data de pagamento (opcional)" type="date" value={editor.draft.paidAt} onChange={(event) => changeDraft({ paidAt: event.target.value })} />
              <SelectField label="Natureza" value={editor.draft.nature} onChange={(event) => changeDraft({ nature: event.target.value as Draft['nature'] })} options={[{ value: 'FIXED', label: 'Fixa' }, { value: 'VARIABLE', label: 'Variável' }]} />
              <ToggleField label="Recorrente" checked={editor.draft.recurring} onChange={(event) => changeDraft({ recurring: event.target.checked })} />
              <ToggleField label="Paga" checked={editor.draft.paid} onChange={(event) => changeDraft({ paid: event.target.checked })} />
            </>}
            {editor.resource === 'debts' && <>
              <Input label="Tipo de dívida" value={editor.draft.kind} onChange={(event) => changeDraft({ kind: event.target.value })} placeholder="financiamento, cartão..." required />
              <MoneyInput label="Saldo atual (opcional)" value={editor.draft.amount} onChange={(event) => changeDraft({ amount: event.target.value })} />
              <MoneyInput label="Parcela mensal (opcional)" value={editor.draft.monthlyPayment} onChange={(event) => changeDraft({ monthlyPayment: event.target.value })} />
              <MoneyInput label="Taxa anual % (opcional)" value={editor.draft.interestRate} step="0.000001" onChange={(event) => changeDraft({ interestRate: event.target.value })} />
              <Input label="Vencimento (opcional)" type="date" value={editor.draft.date} onChange={(event) => changeDraft({ date: event.target.value })} />
              <Input label="Saldo apurado em (opcional)" type="date" value={editor.draft.secondaryDate} onChange={(event) => changeDraft({ secondaryDate: event.target.value })} />
              <Input label="Moeda" value={editor.draft.currency} maxLength={3} onChange={(event) => changeDraft({ currency: event.target.value.toUpperCase() })} required />
              <SelectField label="Status" value={editor.draft.liabilityStatus} onChange={(event) => changeDraft({ liabilityStatus: event.target.value as Draft['liabilityStatus'] })} options={[{ value: 'ACTIVE', label: 'Ativa' }, { value: 'PAID', label: 'Paga' }, { value: 'DEFAULTED', label: 'Inadimplente' }, { value: 'CANCELLED', label: 'Cancelada' }]} />
            </>}
            {editor.resource === 'assets' && <>
              <SelectField label="Classe" value={editor.draft.assetClass} onChange={(event) => changeDraft({ assetClass: event.target.value as Draft['assetClass'] })} options={[{ value: 'CASH', label: 'Dinheiro/conta' }, { value: 'EMERGENCY_RESERVE', label: 'Reserva de emergência' }, { value: 'FIXED_INCOME', label: 'Renda fixa' }, { value: 'INVESTMENTS', label: 'Investimentos' }, { value: 'REAL_ESTATE', label: 'Imóvel' }, { value: 'VEHICLES', label: 'Veículo' }, { value: 'OTHER', label: 'Outro' }]} />
              <MoneyInput label="Valor atual (opcional)" value={editor.draft.amount} onChange={(event) => changeDraft({ amount: event.target.value })} />
              <Input label="Valor apurado em (opcional)" type="date" value={editor.draft.date} onChange={(event) => changeDraft({ date: event.target.value })} />
              <Input label="Moeda" value={editor.draft.currency} maxLength={3} onChange={(event) => changeDraft({ currency: event.target.value.toUpperCase() })} required />
              <SelectField label="Status" value={editor.draft.assetStatus} onChange={(event) => changeDraft({ assetStatus: event.target.value as Draft['assetStatus'] })} options={[{ value: 'ACTIVE', label: 'Ativo' }, { value: 'DISPOSED', label: 'Baixado/vendido' }]} />
            </>}
            {editor.resource === 'goals' && <>
              <MoneyInput label="Valor alvo" value={editor.draft.amount} min="0.01" onChange={(event) => changeDraft({ amount: event.target.value })} required />
              <MoneyInput label="Valor atual (opcional)" value={editor.draft.currentAmount} onChange={(event) => changeDraft({ currentAmount: event.target.value })} />
              <Input label="Prazo (opcional)" type="date" value={editor.draft.date} onChange={(event) => changeDraft({ date: event.target.value })} />
              <SelectField label="Prioridade" value={editor.draft.priority} onChange={(event) => changeDraft({ priority: event.target.value as Draft['priority'] })} options={[{ value: 'LOW', label: 'Baixa' }, { value: 'MEDIUM', label: 'Média' }, { value: 'HIGH', label: 'Alta' }]} />
              <Input label="Moeda" value={editor.draft.currency} maxLength={3} onChange={(event) => changeDraft({ currency: event.target.value.toUpperCase() })} required />
              <SelectField label="Status" value={editor.draft.goalStatus} onChange={(event) => changeDraft({ goalStatus: event.target.value as Draft['goalStatus'] })} options={[{ value: 'ACTIVE', label: 'Ativo' }, { value: 'PAUSED', label: 'Pausado' }, { value: 'COMPLETED', label: 'Concluído' }, { value: 'CANCELLED', label: 'Cancelado' }]} />
            </>}
            <Button type="submit" disabled={pendingMutation}>{pendingMutation ? 'Salvando...' : 'Salvar'}</Button>
          </form>
        )}
      </Modal>

      <Modal open={pendingSwitchId !== null} title="Alterações não salvas" onClose={() => setPendingSwitchId(null)}>
        <p>Trocar de household descartará o formulário atual. Nenhum dado será movido para outro household.</p>
        <div className="vn-inline-actions"><Button variant="secondary" onClick={() => setPendingSwitchId(null)}>Cancelar</Button><Button onClick={discardAndSwitch}>Descartar e trocar</Button></div>
      </Modal>
    </section>
  );
}
