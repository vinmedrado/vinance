import { api } from '../../../services/api';
import type { Expense, ExpenseCreate, FinancialDiagnosis, FinancialProfile, FinancialProfileCreate, Income, IncomeCreate } from '../types/financial.types';

export async function getDiagnosis() { const { data } = await api.get<FinancialDiagnosis>('/financial/diagnosis'); return data; }
export async function listIncomes() { const { data } = await api.get<Income[]>('/financial/incomes'); return data; }
export async function createIncome(payload: IncomeCreate) { const { data } = await api.post<Income>('/financial/incomes', payload); return data; }
export async function listExpenses() { const { data } = await api.get<Expense[]>('/financial/expenses'); return data; }
export async function createExpense(payload: ExpenseCreate) { const { data } = await api.post<Expense>('/financial/expenses', payload); return data; }
export async function getProfile() { const { data } = await api.get<FinancialProfile>('/financial/profile'); return data; }
export async function upsertProfile(payload: FinancialProfileCreate) { const { data } = await api.post<FinancialProfile>('/financial/profile', payload); return data; }
