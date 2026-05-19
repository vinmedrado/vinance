import { api } from './api';

export type RiskProfile = 'conservador' | 'moderado' | 'arrojado' | 'agressivo';

export type InvestmentDecisionInput = {
  monthly_income: number;
  monthly_expenses: number;
  cash_available: number;
  emergency_reserve_current: number;
  risk_profile: RiskProfile;
  horizon_months: number;
  objective: string;
};

export type BacktestInput = {
  ticker: string;
  initial_capital: number;
  monthly_contribution: number;
  strategy: string;
  horizon_months: number;
  risk_profile: RiskProfile;
};

export type TrainModelInput = {
  market: string;
  risk_profile: RiskProfile;
  horizon_months: number;
  capital: number;
};

export async function getQuantHealth() {
  const { data } = await api.get('/quant/health');
  return data;
}

export async function getQuantMarkets() {
  const { data } = await api.get('/quant/markets');
  return data;
}

export async function syncQuantMarketData() {
  const { data } = await api.post('/quant/market-data/sync');
  return data;
}

export async function runInvestmentDecision(input: InvestmentDecisionInput) {
  const { data } = await api.post('/quant/investment-decision', input);
  return data;
}

export async function runQuantBacktest(input: BacktestInput) {
  const { data } = await api.post('/quant/backtest/run', input);
  return data;
}

export async function runQuantBacktestAsync(input: BacktestInput) {
  const { data } = await api.post('/quant/backtest/async', input);
  return data;
}

export async function trainQuantModel(input: TrainModelInput) {
  const { data } = await api.post('/quant/ml/train', input);
  return data;
}

export async function trainQuantModelAsync(input: TrainModelInput) {
  const { data } = await api.post('/quant/ml/train/async', input);
  return data;
}

export async function getQuantJob(jobId: string) {
  const { data } = await api.get(`/quant/jobs/${jobId}`);
  return data;
}

export async function getQuantRuns() {
  const { data } = await api.get('/quant/runs');
  return data;
}
