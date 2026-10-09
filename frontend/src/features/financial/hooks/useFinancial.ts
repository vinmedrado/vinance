import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSessionToken } from '../../auth/hooks/useAuth';
import { createExpense, createIncome, getDiagnosis, getProfile, listExpenses, listIncomes, upsertProfile } from '../services/financial.service';

export function useFinancialDiagnosis() { const token = useSessionToken(); return useQuery({ queryKey: ['financial', token, 'diagnosis'], queryFn: getDiagnosis }); }
export function useIncomes() { const token = useSessionToken(); return useQuery({ queryKey: ['financial', token, 'incomes'], queryFn: listIncomes }); }
export function useExpenses() { const token = useSessionToken(); return useQuery({ queryKey: ['financial', token, 'expenses'], queryFn: listExpenses }); }
export function useFinancialProfile() { const token = useSessionToken(); return useQuery({ queryKey: ['financial', token, 'profile'], queryFn: getProfile, retry: false }); }
export function useCreateIncome() { const qc = useQueryClient(); return useMutation({ mutationFn: createIncome, onSuccess: () => { qc.invalidateQueries({ queryKey: ['financial'] }); } }); }
export function useCreateExpense() { const qc = useQueryClient(); return useMutation({ mutationFn: createExpense, onSuccess: () => { qc.invalidateQueries({ queryKey: ['financial'] }); } }); }
export function useUpsertProfile() { const qc = useQueryClient(); return useMutation({ mutationFn: upsertProfile, onSuccess: () => { qc.invalidateQueries({ queryKey: ['financial'] }); } }); }
export function useScopedUpsertProfile() {
  const qc = useQueryClient();
  const token = useSessionToken();
  return useMutation({
    mutationFn: (request: { sessionToken: string | null; payload: Parameters<typeof upsertProfile>[0] }) => {
      if (request.sessionToken !== token) throw new Error('A sessão mudou. Revise o perfil antes de salvar.');
      return upsertProfile(request.payload);
    },
    onSuccess: (_data, request) => {
      qc.invalidateQueries({ queryKey: ['financial', request.sessionToken, 'profile'] });
      qc.invalidateQueries({ queryKey: ['financial-state', request.sessionToken] });
    },
  });
}
