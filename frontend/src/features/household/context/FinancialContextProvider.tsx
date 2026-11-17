import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react';
import { Button, Modal } from '../../../components';
import { useSessionToken } from '../../auth/hooks/useAuth';
import {
  useHouseholdDefault,
  useHouseholdList,
  useSetDefaultHousehold,
} from '../hooks/useHousehold';
import type { Household } from '../types/household.types';

export type FinancialContextSwitchGuard = {
  isDirty: () => boolean;
  discard: () => void;
};

type FinancialContextValue = {
  activeHousehold: Household | null;
  personalHousehold: Household | null;
  sharedHouseholds: Household[];
  households: Household[];
  label: string;
  description: string;
  isLoading: boolean;
  isSwitching: boolean;
  error: unknown;
  switchContext: (householdId: number) => Promise<boolean>;
  registerSwitchGuard: (guard: FinancialContextSwitchGuard) => () => void;
};

const FinancialContext = createContext<FinancialContextValue | null>(null);

function isHousehold(value: unknown): value is Household {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<Household>;
  return (
    typeof candidate.id === 'number'
    && typeof candidate.name === 'string'
    && (candidate.household_type === 'PERSONAL' || candidate.household_type === 'SHARED')
    && (candidate.status === 'ACTIVE' || candidate.status === 'ARCHIVED')
  );
}
export function normalizeHouseholds(value: unknown): Household[] {
  return Array.isArray(value) ? value.filter(isHousehold) : [];
}

export function normalizeHousehold(value: unknown): Household | null {
  return isHousehold(value) ? value : null;
}

export function financialContextCopy(household: Household | null) {
  if (!household) {
    return {
      label: 'Contexto indisponível',
      description: 'Não foi possível determinar quais dados financeiros estão ativos.',
    };
  }
  if (household?.household_type === 'SHARED') {
    return {
      label: 'Finanças do casal',
      description: 'Informações compartilhadas, disponíveis para os integrantes autorizados da conta conjunta.',
    };
  }
  return {
    label: 'Minhas finanças',
    description: 'Informações particulares, visíveis somente para você.',
  };
}

export function FinancialContextProvider({ children }: PropsWithChildren) {
  const sessionToken = useSessionToken();
  const householdList = useHouseholdList();
  const defaultHousehold = useHouseholdDefault();
  const setDefault = useSetDefaultHousehold();
  const setDefaultHousehold = setDefault.mutateAsync;
  const guards = useRef(new Set<FinancialContextSwitchGuard>());
  const [pendingHouseholdId, setPendingHouseholdId] = useState<number | null>(null);
  const [switchError, setSwitchError] = useState<unknown>(null);

  const households = useMemo(
    () => normalizeHouseholds(householdList.data).filter((item) => item.status === 'ACTIVE'),
    [householdList.data],
  );
  const activeHousehold = normalizeHousehold(defaultHousehold.data);
  const personalHousehold = households.find((item) => item.household_type === 'PERSONAL') ?? null;
  const sharedHouseholds = households.filter((item) => item.household_type === 'SHARED');
  const copy = financialContextCopy(activeHousehold);

  const registerSwitchGuard = useCallback((guard: FinancialContextSwitchGuard) => {
    guards.current.add(guard);
    return () => guards.current.delete(guard);
  }, []);

  const performSwitch = useCallback(async (householdId: number) => {
    if (householdId === activeHousehold?.id) return true;
    if (!households.some((item) => item.id === householdId)) return false;
    setSwitchError(null);
    try {
      await setDefaultHousehold({ householdId, sessionToken, payload: undefined });
      return true;
    } catch (error) {
      setSwitchError(error);
      throw error;
    }
  }, [activeHousehold?.id, households, sessionToken, setDefaultHousehold]);

  const switchContext = useCallback(async (householdId: number) => {
    if (householdId === activeHousehold?.id) return true;
    if ([...guards.current].some((guard) => guard.isDirty())) {
      setPendingHouseholdId(householdId);
      return false;
    }
    return performSwitch(householdId);
  }, [activeHousehold?.id, performSwitch]);

  async function confirmSwitch() {
    if (pendingHouseholdId === null) return;
    const destination = pendingHouseholdId;
    try {
      const switched = await performSwitch(destination);
      if (!switched) return;
      for (const guard of guards.current) {
        if (guard.isDirty()) guard.discard();
      }
      setPendingHouseholdId(null);
    } catch {
      // The mutation exposes its sanitized error through the context. Keep
      // the confirmation open and the user's draft intact for a safe retry.
    }
  }

  const value = useMemo<FinancialContextValue>(() => ({
    activeHousehold,
    personalHousehold,
    sharedHouseholds,
    households,
    label: copy.label,
    description: copy.description,
    isLoading: householdList.isLoading || defaultHousehold.isLoading,
    isSwitching: setDefault.isPending,
    error: householdList.error || defaultHousehold.error || setDefault.error || switchError,
    switchContext,
    registerSwitchGuard,
  }), [
    activeHousehold,
    copy.description,
    copy.label,
    defaultHousehold.error,
    defaultHousehold.isLoading,
    householdList.error,
    householdList.isLoading,
    households,
    personalHousehold,
    registerSwitchGuard,
    setDefault.error,
    setDefault.isPending,
    sharedHouseholds,
    switchError,
    switchContext,
  ]);

  return (
    <FinancialContext.Provider value={value}>
      {children}
      <Modal
        open={pendingHouseholdId !== null}
        title="Mudar de contexto financeiro?"
        onClose={() => setPendingHouseholdId(null)}
      >
        <div className="vn-context-confirmation">
          <p>Há alterações não salvas. Para evitar registrar dados no lugar errado, revise o formulário ou descarte o rascunho antes de mudar.</p>
          {Boolean(switchError) && (
            <p className="vn-context-confirmation__error" role="alert">
              Não foi possível mudar o contexto. Seu rascunho foi preservado. Tente novamente.
            </p>
          )}
          <div className="vn-inline-actions">
            <Button variant="secondary" onClick={() => setPendingHouseholdId(null)}>Continuar editando</Button>
            <Button onClick={confirmSwitch} disabled={setDefault.isPending}>
              {setDefault.isPending ? 'Mudando…' : 'Descartar e mudar'}
            </Button>
          </div>
        </div>
      </Modal>
    </FinancialContext.Provider>
  );
}

export function useFinancialContext() {
  const value = useContext(FinancialContext);
  if (!value) throw new Error('useFinancialContext must be used inside FinancialContextProvider');
  return value;
}
