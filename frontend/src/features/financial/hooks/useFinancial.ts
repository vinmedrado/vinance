import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createExpense, createIncome, getDiagnosis, getProfile, listExpenses, listIncomes, upsertProfile } from '../services/financial.service';

export function useFinancialDiagnosis() { return useQuery({ queryKey: ['financial', 'diagnosis'], queryFn: getDiagnosis }); }
export function useIncomes() { return useQuery({ queryKey: ['financial', 'incomes'], queryFn: listIncomes }); }
export function useExpenses() { return useQuery({ queryKey: ['financial', 'expenses'], queryFn: listExpenses }); }
export function useFinancialProfile() { return useQuery({ queryKey: ['financial', 'profile'], queryFn: getProfile, retry: false }); }
export function useCreateIncome() { const qc = useQueryClient(); return useMutation({ mutationFn: createIncome, onSuccess: () => { qc.invalidateQueries({ queryKey: ['financial'] }); } }); }
export function useCreateExpense() { const qc = useQueryClient(); return useMutation({ mutationFn: createExpense, onSuccess: () => { qc.invalidateQueries({ queryKey: ['financial'] }); } }); }
export function useUpsertProfile() { const qc = useQueryClient(); return useMutation({ mutationFn: upsertProfile, onSuccess: () => { qc.invalidateQueries({ queryKey: ['financial'] }); } }); }
