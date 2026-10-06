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
