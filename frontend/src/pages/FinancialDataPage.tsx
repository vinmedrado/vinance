import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button, Card, EmptyState, ErrorState, Input, LoadingState, Modal, MoneyInput, SectionHeader, SelectField, Toast, ToggleField } from '../components';
import { useCurrentUser, useSessionToken } from '../features/auth/hooks/useAuth';
import { OwnershipDestinationField } from '../features/financial-state/components/OwnershipDestinationField';
import { TransferFinancialRecordsDialog } from '../features/financial-state/components/TransferFinancialRecordsDialog';
import { useFinancialProfile, useScopedUpsertProfile } from '../features/financial/hooks/useFinancial';
import {
  useCreateFinancialResource,
  useDeleteFinancialResource,
  useFinancialResourceList,
  useUpdateFinancialResource,
  type FinancialResource,
  type FinancialResourceItem,
} from '../features/financial-state/hooks/useFinancialResources';
import type { FinancialTransferResource, OwnershipScope } from '../features/financial-state/types/financialState.types';
import { useFinancialContext } from '../features/household/context/FinancialContextProvider';
import { useHouseholdMembers } from '../features/household/hooks/useHousehold';
import { formatCurrency } from '../utils/formatters';
import { riskProfileLabel } from '../features/intelligence/utils/presentation';
import { localDateInputValue } from '../utils/localDate';
import type { ApiErrorShape } from '../services/api';

type EditorMode = 'create' | 'edit';
type Draft = {
  scope: OwnershipScope;
  destinationHouseholdId: number | null;
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

function resourceArticle(resource: FinancialResource) {
  return resource === 'assets' || resource === 'goals' ? 'este' : 'esta';
}

function resourceEmptyTitle(resource: FinancialResource) {
  const masculine = resource === 'assets' || resource === 'goals';
  return `${masculine ? 'Nenhum' : 'Nenhuma'} ${labels[resource].singular} cadastrad${masculine ? 'o' : 'a'}`;
}

function resourceDeletedMessage(resource: FinancialResource) {
  const masculine = resource === 'assets' || resource === 'goals';
  const name = `${labels[resource].singular[0].toUpperCase()}${labels[resource].singular.slice(1)}`;
  return `${name} excluíd${masculine ? 'o' : 'a'}.`;
}

function emptyDraft(): Draft {
  return {
    scope: 'PERSONAL',
    destinationHouseholdId: null,
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
  draft.destinationHouseholdId = item.household_id;
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
  const financialContext = useFinancialContext();
  const profile = useFinancialProfile();
  const saveProfile = useScopedUpsertProfile();
  const [editor, setEditor] = useState<Editor | null>(null);
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileDirty, setProfileDirty] = useState(false);
  const [profileDraft, setProfileDraft] = useState(emptyProfileDraft);
  const [notice, setNotice] = useState<string | null>(null);
  const [selectedTransferIds, setSelectedTransferIds] = useState<Record<FinancialTransferResource, number[]>>({
    incomes: [],
    expenses: [],
  });
  const [transferResource, setTransferResource] = useState<FinancialTransferResource | null>(null);
  const [transferRecordIds, setTransferRecordIds] = useState<number[]>([]);
  const [transferTargetId, setTransferTargetId] = useState<number | null>(null);
  const [reviewPromptDismissed, setReviewPromptDismissed] = useState(true);
  const previousSession = useRef(sessionToken);
  const selectedId = financialContext.activeHousehold?.id ?? null;

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
  const selectedHousehold = financialContext.activeHousehold;
  const currentMembership = members.data?.find((item) => item.user_id === currentUser.data?.id);
  const pendingMutation = createResource.isPending || updateResource.isPending || deleteResource.isPending || saveProfile.isPending;
  const missingProfile = (profile.error as ApiErrorShape | null)?.status === 404;
  const loadError = financialContext.error || members.error || (!missingProfile && profile.error) || resources.map((resource) => queryByResource[resource].error).find(Boolean);
  const actionError = createResource.error || updateResource.error || deleteResource.error || saveProfile.error;

  useEffect(() => financialContext.registerSwitchGuard({
    isDirty: () => Boolean(editor || profileEditing || profileDirty),
    discard: () => {
      setEditor(null);
      setProfileEditing(false);
      setProfileDirty(false);
    },
  }), [editor, financialContext.registerSwitchGuard, profileDirty, profileEditing]);

  useEffect(() => {
    setSelectedTransferIds({ incomes: [], expenses: [] });
    setTransferResource(null);
    setTransferRecordIds([]);
  }, [selectedId]);

  useEffect(() => {
    if (financialContext.sharedHouseholds.length === 1) {
      setTransferTargetId(financialContext.sharedHouseholds[0].id);
      return;
    }
    if (!financialContext.sharedHouseholds.some((household) => household.id === transferTargetId)) {
      setTransferTargetId(null);
    }
  }, [financialContext.sharedHouseholds, transferTargetId]);

  useEffect(() => {
    if (!currentUser.data?.id || !selectedHousehold) return;
    const reviewKey = `vinance:personal-transfer-review:${currentUser.data.id}:${selectedHousehold.id}`;
    setReviewPromptDismissed(
      selectedHousehold.household_type !== 'PERSONAL' || window.localStorage.getItem(reviewKey) === 'dismissed',
    );
  }, [currentUser.data?.id, selectedHousehold]);

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
    setEditor(null);
    setProfileEditing(false);
    setProfileDirty(false);
    setProfileDraft(emptyProfileDraft());
    setSelectedTransferIds({ incomes: [], expenses: [] });
    setTransferResource(null);
    setTransferRecordIds([]);
    setNotice(null);
  }, [sessionToken]);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 3500);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  const groupedCounts = useMemo(() => Object.fromEntries(resources.map((resource) => [
    resource,
    ((queryByResource[resource].data ?? []) as FinancialResourceItem[]).filter(
      (item) => item.ownership_scope === 'HOUSEHOLD' || item.user_id === currentUser.data?.id,
    ).length,
  ])), [assets.data, currentUser.data?.id, debts.data, expenses.data, goals.data, incomes.data]);

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
    const payload = payloadFromDraft(editor.resource, editor.draft);
    if (editor.mode === 'create') {
      let destinationHouseholdId = editor.householdId;
      if (editor.resource === 'incomes' || editor.resource === 'expenses') {
        const destination = financialContext.households.find(
          (household) => household.id === editor.draft.destinationHouseholdId,
        );
        if (!destination) throw new Error('Escolha onde deseja registrar este lançamento.');
        destinationHouseholdId = destination.id;
        (payload as { ownership_scope: OwnershipScope }).ownership_scope = destination.household_type === 'PERSONAL'
          ? 'PERSONAL'
          : 'HOUSEHOLD';
      }
      await createResource.mutateAsync({
        householdId: destinationHouseholdId,
        sessionToken: editor.sessionToken,
        resource: editor.resource,
        payload,
      });
      const destination = financialContext.households.find((household) => household.id === destinationHouseholdId);
      const resourceName = labels[editor.resource].singular[0].toUpperCase() + labels[editor.resource].singular.slice(1);
      const destinationLabel = destination?.household_type === 'SHARED' ? 'Finanças do casal' : 'Minhas finanças';
      setNotice(`${resourceName} registrada em ${destinationLabel}.`);
    } else {
      if (editor.resource === 'incomes' || editor.resource === 'expenses' || editor.ownerUserId !== currentUser.data?.id) {
        delete (payload as { ownership_scope?: OwnershipScope }).ownership_scope;
      }
      await updateResource.mutateAsync({ householdId: editor.householdId, sessionToken: editor.sessionToken, resource: editor.resource, recordId: editor.recordId as number, payload });
      setNotice(`${labels[editor.resource].singular[0].toUpperCase()}${labels[editor.resource].singular.slice(1)} atualizada com sucesso.`);
    }
    setEditor(null);
  }

  function toggleTransferSelection(resource: FinancialTransferResource, recordId: number) {
    setSelectedTransferIds((current) => ({
      ...current,
      [resource]: current[resource].includes(recordId)
        ? current[resource].filter((id) => id !== recordId)
        : [...current[resource], recordId],
    }));
  }

  function openTransfer(resource: FinancialTransferResource, recordIds: number[]) {
    if (recordIds.length === 0 || transferTargetId === null) return;
    setTransferResource(resource);
    setTransferRecordIds(recordIds);
  }

  function closeTransfer() {
    setTransferResource(null);
    setTransferRecordIds([]);
  }

  function transferred(count: number) {
    if (transferResource) {
      setSelectedTransferIds((current) => ({ ...current, [transferResource]: [] }));
    }
    const label = transferResource === 'incomes'
      ? (count === 1 ? 'receita transferida' : 'receitas transferidas')
      : (count === 1 ? 'despesa transferida' : 'despesas transferidas');
    setNotice(`${count} ${label} para Finanças do casal.`);
    closeTransfer();
  }

  function dismissReviewPrompt() {
    if (!currentUser.data?.id || !selectedHousehold) return;
    window.localStorage.setItem(
      `vinance:personal-transfer-review:${currentUser.data.id}:${selectedHousehold.id}`,
      'dismissed',
    );
    setReviewPromptDismissed(true);
  }

  async function remove(resource: FinancialResource, item: FinancialResourceItem) {
    if (selectedId === null || !window.confirm(`Excluir ${resourceArticle(resource)} ${labels[resource].singular}? Seu plano será reavaliado quando aplicável.`)) return;
    await deleteResource.mutateAsync({ householdId: selectedId, sessionToken, resource, recordId: item.id });
    setNotice(resourceDeletedMessage(resource));
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

  const transferTarget = financialContext.sharedHouseholds.find((household) => household.id === transferTargetId) ?? null;
  const hasReviewableExpenses = selectedHousehold?.household_type === 'PERSONAL'
    && (expenses.data ?? []).some(
      (item) => item.ownership_scope === 'PERSONAL' && item.user_id === currentUser.data?.id,
    );

  if (financialContext.isLoading || currentUser.isLoading) return <LoadingState label="Carregando seus dados financeiros..." />;

  return (
    <section className="vn-page">
      <SectionHeader eyebrow="Dados financeiros" title="Gerenciar minha vida financeira" description="Cadastre apenas o que conhece. Campo vazio continua desconhecido — nunca vira zero automaticamente." />
      {loadError && <Card><ErrorState title="Não foi possível carregar seus dados" description={errorMessage(loadError)} /></Card>}
      {actionError && <Card><ErrorState title="A alteração não foi salva" description={errorMessage(actionError)} /></Card>}
      {notice && <Toast message={notice} />}

      {!reviewPromptDismissed && hasReviewableExpenses && financialContext.sharedHouseholds.length > 0 && (
        <aside className="vn-context-guidance vn-context-guidance--review" aria-label="Revisão de despesas pessoais">
          <div>
            <strong>Registrou alguma despesa da casa em Minhas finanças?</strong>
            <p>Revise apenas os lançamentos que deseja compartilhar. Nada será movido automaticamente.</p>
          </div>
          <div className="vn-inline-actions">
            <Button
              variant="secondary"
              onClick={() => document.querySelector('[data-financial-resource="expenses"]')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            >
              Revisar lançamentos
            </Button>
            <Button variant="ghost" onClick={dismissReviewPrompt}>Dispensar</Button>
          </div>
        </aside>
      )}

      {selectedHousehold?.household_type === 'PERSONAL' && financialContext.sharedHouseholds.length > 1 && (
        <div className="vn-transfer-target">
          <SelectField
            label="Destino das transferências"
            value={transferTargetId ?? ''}
            onChange={(event) => setTransferTargetId(Number(event.target.value))}
            options={[
              { value: '', label: 'Selecione as Finanças do casal' },
              ...financialContext.sharedHouseholds.map((household) => ({ value: String(household.id), label: household.name })),
            ]}
            helper="Escolha explicitamente qual conta compartilhada receberá os lançamentos."
          />
        </div>
      )}

      <div className="vn-grid vn-grid--two">
        {resources.map((resource) => {
          const query = queryByResource[resource];
          const items = ((query.data ?? []) as FinancialResourceItem[]).filter(
            (item) => item.ownership_scope === 'HOUSEHOLD' || item.user_id === currentUser.data?.id,
          );
          const transferKind = resource === 'incomes' || resource === 'expenses' ? resource : null;
          const selectedIds = transferKind ? selectedTransferIds[transferKind] : [];
          return (
            <div key={resource} data-financial-resource={resource}>
            <Card title={labels[resource].plural} description={`${labels[resource].description} ${groupedCounts[resource]} cadastrado(s).`} action={<Button onClick={() => openCreate(resource)}>Adicionar</Button>}>
              {query.isLoading ? <LoadingState label={`Carregando ${labels[resource].plural.toLowerCase()}...`} /> : items.length === 0 ? (
                <EmptyState title={resourceEmptyTitle(resource)} description="Você pode adicionar agora ou voltar depois se ainda não souber a informação." action={<Button variant="secondary" onClick={() => openCreate(resource)}>Adicionar {labels[resource].singular}</Button>} />
              ) : (
                <div className="vn-list">
                  {items.map((item) => {
                    const canMutate = item.user_id === currentUser.data?.id
                      || (item.ownership_scope === 'HOUSEHOLD' && currentMembership?.role === 'OWNER');
                    const canTransfer = Boolean(
                      transferKind
                      && selectedHousehold?.household_type === 'PERSONAL'
                      && financialContext.sharedHouseholds.length > 0
                      && item.ownership_scope === 'PERSONAL'
                      && item.user_id === currentUser.data?.id,
                    );
                    return (
                    <div key={item.id}>
                      <div>
                        {canTransfer && transferKind && (
                          <label className="vn-transfer-select">
                            <input
                              type="checkbox"
                              checked={selectedIds.includes(item.id)}
                              onChange={() => toggleTransferSelection(transferKind, item.id)}
                              aria-label={`Selecionar ${itemTitle(resource, item)} para transferência`}
                            />
                            <span className="vn-sr-only">Selecionar para transferência</span>
                          </label>
                        )}
                        <strong>{itemTitle(resource, item)}</strong>
                        <p>{money(itemAmount(resource, item))} · {itemScope(item) === 'PERSONAL' ? 'Só eu' : `Compartilhado com ${selectedHousehold?.name ?? 'a casa'}`}</p>
                      </div>
                      <div className="vn-inline-actions">
                        <Badge tone={itemScope(item) === 'PERSONAL' ? 'warning' : 'success'}>{itemScope(item) === 'PERSONAL' ? 'Pessoal' : 'Compartilhado'}</Badge>
                        {canTransfer && transferKind && (
                          <Button
                            variant="secondary"
                            disabled={transferTarget === null}
                            onClick={() => openTransfer(transferKind, [item.id])}
                          >
                            Mover para Finanças do casal
                          </Button>
                        )}
                        {canMutate && <Button variant="secondary" onClick={() => openEdit(resource, item)}>Editar</Button>}
                        {canMutate && <Button variant="ghost" disabled={pendingMutation} onClick={() => remove(resource, item)}>Excluir</Button>}
                      </div>
                    </div>
                    );
                  })}
                </div>
              )}
              {transferKind && selectedIds.length > 0 && (
                <div className="vn-transfer-batch">
                  <span>{selectedIds.length} {selectedIds.length === 1 ? 'lançamento selecionado' : 'lançamentos selecionados'}</span>
                  <Button disabled={transferTarget === null} onClick={() => openTransfer(transferKind, selectedIds)}>
                    Transferir seleção
                  </Button>
                </div>
              )}
            </Card>
            </div>
          );
        })}
      </div>

      <Card title="Meu perfil financeiro" description="Este perfil é pessoal e não é o mesmo que seu perfil de investidor." action={<Button variant="secondary" onClick={() => setProfileEditing((value) => !value)}>{profileEditing ? 'Fechar' : profile.data ? 'Editar perfil' : 'Criar perfil'}</Button>}>
        {!profileEditing && profile.data && (
          <div className="vn-grid vn-grid--three">
            <div><small>Renda líquida mensal</small><strong>{formatCurrency(profile.data.monthly_salary)}</strong></div>
            <div><small>Reserva de emergência atual</small><strong>{formatCurrency(profile.data.emergency_reserve)}</strong></div>
            <div><small>Postura de risco</small><strong>{riskProfileLabel(profile.data.risk_profile)}</strong></div>
            <div><small>Horizonte de investimento</small><strong>{profile.data.investment_horizon_months == null ? 'Não informado' : `${profile.data.investment_horizon_months} meses`}</strong></div>
          </div>
        )}
        {!profileEditing && missingProfile && <EmptyState title="Perfil ainda não preenchido" description="Informe o básico para melhorar a leitura financeira. Você poderá editar depois." />}
        {profileEditing && (
          <form className="vn-form" onSubmit={submitProfile}>
            <MoneyInput label="Renda líquida mensal" helper="Some as entradas recorrentes líquidas do mês, mesmo quando são recebidas em datas diferentes." value={profileDraft.monthlySalary} min="0.01" required onChange={(event) => { setProfileDraft((current) => ({ ...current, monthlySalary: event.target.value })); setProfileDirty(true); }} />
            <MoneyInput label="Reserva de emergência atual" helper="Valor disponível hoje para emergências. Zero é válido e não representa informação ausente." value={profileDraft.emergencyReserve} required onChange={(event) => { setProfileDraft((current) => ({ ...current, emergencyReserve: event.target.value })); setProfileDirty(true); }} />
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
            {editor.mode === 'create' && (editor.resource === 'incomes' || editor.resource === 'expenses') && (
              <OwnershipDestinationField
                name={`financial-data-${editor.resource}-destination`}
                households={financialContext.households}
                value={editor.draft.destinationHouseholdId}
                suggestedHouseholdId={selectedId}
                onChange={(destinationHouseholdId) => changeDraft({ destinationHouseholdId })}
              />
            )}
            {(editor.resource === 'debts' || editor.resource === 'assets' || editor.resource === 'goals') && (
              <SelectField
                label="Quem pode ver este dado?"
                value={editor.draft.scope}
                disabled={editor.mode === 'edit' && editor.ownerUserId !== currentUser.data?.id}
                onChange={(event) => changeDraft({ scope: event.target.value as OwnershipScope })}
                options={[
                  { value: 'PERSONAL', label: 'Só eu' },
                  { value: 'HOUSEHOLD', label: `Compartilhado com ${selectedHousehold?.name ?? 'a casa'}` },
                ]}
                helper={editor.mode === 'edit' && editor.ownerUserId !== currentUser.data?.id
                  ? 'Somente quem criou o registro pode alterar seu compartilhamento.'
                  : 'Compartilhar exige sua escolha explícita.'}
              />
            )}
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

      <TransferFinancialRecordsDialog
        open={transferResource !== null && transferRecordIds.length > 0}
        resource={transferResource ?? 'expenses'}
        recordIds={transferRecordIds}
        targetHousehold={transferTarget}
        onClose={closeTransfer}
        onTransferred={transferred}
      />
    </section>
  );
}
