import axios from 'axios';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';
const baseURL = import.meta.env.VITE_API_URL || '/api';

export const api = axios.create({ baseURL });

const demoUser = {
  id: 'demo-user',
  email: 'demo@vinance.local',
  full_name: 'Demo Vinance',
  organization_id: 'demo-org',
};

const demoDashboard = {
  metrics: {
    total_income: 2000,
    total_expenses: 700,
    monthly_balance: 1300,
    available_to_invest: 360,
    invested_pct: 18,
    realized_investment: 360,
    financial_score: 82,
  },
  budget: {
    monthly_income: 2000,
    actual: { expenses: 700 },
  },
  intelligent_allocation: {
    decision: 'Você possui margem para investir mantendo equilíbrio financeiro.',
    can_invest: true,
    investable_amount: 360,
    method: {
      name: '50/30/20 adaptativo',
      reason: 'Modelo ajustado ao perfil financeiro.',
      needs_pct: 50,
      wants_pct: 30,
      investments_pct: 20,
    },
    risk_profile: 'moderado',
    emergency_reserve_target: 6000,
    emergency_reserve_gap: 4700,
    next_action: 'Continue construindo reserva e mantendo aportes.',
    expense_ratio_pct: 35,
    markets: [
      { name: 'Tesouro Selic', market: 'Renda fixa', risk: 'baixo', reason: 'Liquidez e segurança', allocation_pct: 60, amount: 216 },
      { name: 'ETF Global', market: 'Renda variável', risk: 'moderado', reason: 'Crescimento de longo prazo', allocation_pct: 40, amount: 144 },
    ],
    advisor_notes: ['Modo demonstração', 'Dados simulados', 'Portfolio preview'],
  },
  recommendation: {
    title: 'Plano financeiro recomendado',
    message: 'O Vinance identificou margem saudável para evolução financeira.',
    amount: 360,
  },
  charts: {
    evolution: [
      { month: 'Jan', receitas: 1800, despesas: 900 },
      { month: 'Fev', receitas: 1900, despesas: 850 },
      { month: 'Mar', receitas: 2000, despesas: 780 },
      { month: 'Abr', receitas: 2000, despesas: 730 },
      { month: 'Mai', receitas: 2000, despesas: 700 },
    ],
    by_category: [
      { name: 'Mercado', value: 300 },
      { name: 'Cartão', value: 250 },
      { name: 'Transporte', value: 150 },
    ],
  },
  alerts: [
    { title: 'Reserva em evolução', message: 'Continue fortalecendo sua reserva financeira.', severity: 'info' },
    { title: 'Boa margem mensal', message: 'Seu fluxo financeiro demonstra estabilidade.', severity: 'success' },
  ],
};

const demoAdvisor = {
  year: 2026,
  month: 5,
  health: {
    health_score: 82,
    risk_level: 'baixo',
    financial_phase: 'construção patrimonial',
    evolution_trend: 'estável',
    metrics: { expense_ratio_pct: 35, debt_ratio_pct: 20, reserve_months: 0, savings_rate_pct: 65 },
    input_summary: { monthly_income: 2000, total_expenses: 700, debt_payments: 400, overdue_bills: 0, emergency_reserve: 0, investment_capacity: 360 },
  },
  memory: {
    memory_strength: 'boa',
    patterns: ['rotina financeira estável', 'consistência de aportes'],
    critical_months: [],
    insights: ['Sua rotina está relativamente estável; o próximo ganho vem de consistência e pequenos ajustes.'],
  },
  behavioral_intelligence: {
    behavioral_score: 78,
    stability_score: 86,
    discipline_score: 74,
    risk_behavior_score: 69,
    signals: ['consistência de investimentos'],
  },
  coaching: {
    messages: [
      'Você está na fase de construção patrimonial. O Vinance vai acompanhar sua evolução e ajustar o plano conforme seus dados melhorarem.',
      'Seu fluxo financeiro mostra espaço para planejamento e fortalecimento de reserva.',
    ],
    tips: ['Automatize parte do aporte para manter consistência.'],
    alerts: [{ severity: 'info', message: 'Dados simulados para apresentação de portfólio.' }],
  },
  dynamic_goals: {
    goals: [],
    available_goal_capacity: 360,
    behavior_adjustment: 1,
    allocation_method: '50_30_20',
    allocation_method_label: '50/30/20',
    suggested_limits: { needs: 1000, wants: 500, debts: 100, emergency_reserve: 100, investments: 300 },
    allocation_plan: {
      method: '50_30_20',
      method_label: '50/30/20',
      limits: { needs: 1000, wants: 500, debts: 100, emergency_reserve: 100, investments: 300 },
      safe_to_invest: 360,
      income: 2000,
      expenses: 700,
      surplus: 1300,
      rationale: 'Seu comprometimento está saudável para equilibrar gastos, reserva e investimentos.',
      action_plan: ['Manter gastos essenciais sob controle.', 'Separar parte da sobra para reserva.', 'Direcionar aporte mensal para investimentos.'],
      warnings: [],
      investment_gate: { status: 'enabled', message: 'Você possui margem segura para investir aproximadamente R$ 360,00 neste mês.', safe_amount: 360 },
    },
  },
  forecast: {
    months: 24,
    scenarios: [
      { name: 'pessimista', projected_net_worth: 10560.36 },
      { name: 'base', projected_net_worth: 15467.96 },
      { name: 'otimista', projected_net_worth: 20338.96 },
      { name: 'conservador', projected_net_worth: 15066.22 },
      { name: 'moderado', projected_net_worth: 16285.09 },
      { name: 'agressivo', projected_net_worth: 19720.91 },
    ],
    plain_language_summary: 'A projeção mostra como renda, gastos e constância de aporte podem afetar sua evolução financeira.',
  },
  decision_advisor: {
    decision_type: 'debt_vs_invest',
    title: 'Quitar dívida ou investir?',
    recommendation: 'Mantenha reserva e aporte com controle de risco.',
    reasons: ['Existe margem positiva no mês demonstrativo.'],
    next_steps: ['Manter orçamento mensal atualizado.', 'Priorizar reserva antes de aumentar risco.'],
    confidence: 0.86,
  },
  retention: {
    milestones: [{ type: 'consistency', title: 'Consistência de aportes', description: 'Você manteve margem para aportes no cenário demonstrativo.' }],
    progress_summary: 'Sua evolução começou a aparecer; mantenha o plano por mais alguns ciclos.',
    recurring_insights: ['Pequenos aportes recorrentes fortalecem metas de médio e longo prazo.'],
  },
  timeline: {
    events: [
      { period: '05/2026', type: 'model_change', title: 'Modelo financeiro ajustado', description: 'O plano passou para 50/30/20 adaptativo para acompanhar sua realidade.' },
      { period: '05/2026', type: 'investment_capacity', title: 'Margem para investir', description: 'Foi identificada uma sobra segura para aporte mensal.' },
    ],
    summary: 'Linha do tempo da sua jornada financeira pessoal.',
  },
  advisor_main_message: 'Você está na fase de construção patrimonial. O Vinance vai acompanhar sua evolução e ajustar o plano conforme seus dados melhorarem.',
  next_best_action: 'Monte sua reserva e mantenha aportes consistentes.',
  disclaimer: 'Demo visual com dados simulados para apresentação de portfólio. Isso não constitui recomendação financeira.',
};

const demoResponses: Record<string, any> = {
  '/dashboard': demoDashboard,
  '/api/dashboard': demoDashboard,

  '/incomes': [{ id: 1, description: 'Salário', amount: 2000, received_at: '2026-05-15', status: 'received' }],
  '/api/incomes': [{ id: 1, description: 'Salário', amount: 2000, received_at: '2026-05-15', status: 'received' }],

  '/expenses': [
    { id: 1, description: 'Mercado', amount: 300, due_date: '2026-05-18', status: 'paid' },
    { id: 2, description: 'Cartão', amount: 400, due_date: '2026-05-20', status: 'pending' },
  ],
  '/api/expenses': [
    { id: 1, description: 'Mercado', amount: 300, due_date: '2026-05-18', status: 'paid' },
    { id: 2, description: 'Cartão', amount: 400, due_date: '2026-05-20', status: 'pending' },
  ],

  '/accounts': [{ id: 1, name: 'Conta Principal', type: 'checking', institution: 'Nubank', balance: 1300, status: 'active' }],
  '/api/accounts': [{ id: 1, name: 'Conta Principal', type: 'checking', institution: 'Nubank', balance: 1300, status: 'active' }],

  '/cards': [{ id: 1, name: 'Cartão Casas Bahia', brand: 'Visa', limit_amount: 2500, closing_day: 10, due_day: 20, is_active: true, status: 'active' }],
  '/api/cards': [{ id: 1, name: 'Cartão Casas Bahia', brand: 'Visa', limit_amount: 2500, closing_day: 10, due_day: 20, is_active: true, status: 'active' }],

  '/investments': [],
  '/api/investments': [],
  '/goals': [],
  '/api/goals': [],
  '/alerts': [{ id: 1, title: 'Reserva em construção', message: 'Continue fortalecendo sua reserva antes de aumentar risco.', status: 'info' }],
  '/api/alerts': [{ id: 1, title: 'Reserva em construção', message: 'Continue fortalecendo sua reserva antes de aumentar risco.', status: 'info' }],
  '/portfolio': { positions: [] },
  '/api/portfolio': { positions: [] },

  '/intelligence/ai-financial-advisor': demoAdvisor,
  '/api/intelligence/ai-financial-advisor': demoAdvisor,

  '/quant/runs': [],
  '/api/quant/runs': [],
  '/quant/health': { status: 'ok', mode: 'demo' },
  '/api/quant/health': { status: 'ok', mode: 'demo' },
  '/quant/markets': [],
  '/api/quant/markets': [],
};

function persistSession(data: any) {
  if (data.access_token) localStorage.setItem('financeos_token', data.access_token);
  if (data.refresh_token) localStorage.setItem('financeos_refresh_token', data.refresh_token);
  if (data.user) localStorage.setItem('financeos_user', JSON.stringify(data.user));
  return data;
}

function persistDemoMutation(config: any) {
  const method = String(config.method || '').toLowerCase();
  const rawUrl = String(config.url || '');
  const cleanUrl = rawUrl.replace(/^\/api/, '');
  const normalizedUrl = `/api${cleanUrl}`;

  if (!DEMO_MODE || !['post', 'put', 'patch', 'delete'].includes(method)) {
    return null;
  }

  if (method === 'delete') {
    return { ok: true };
  }

  let body: any = {};
  try {
    body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data || {};
  } catch {
    body = {};
  }

  const created = {
    id: Date.now(),
    status: 'active',
    ...body,
  };

  if (normalizedUrl.includes('/incomes')) return created;
  if (normalizedUrl.includes('/expenses')) return created;
  if (normalizedUrl.includes('/accounts')) return created;
  if (normalizedUrl.includes('/cards')) return created;
  if (normalizedUrl.includes('/goals')) return created;
  if (normalizedUrl.includes('/investments')) return created;

  return { ok: true };
}

export async function login(email: string, password: string) {
  if (DEMO_MODE) {
    return persistSession({
      access_token: 'demo-token',
      refresh_token: 'demo-refresh-token',
      user: {
        ...demoUser,
        email: email || demoUser.email,
      },
    });
  }

  const { data } = await api.post('/auth/login', { email, password });
  return persistSession(data);
}

export async function register(input: {
  email: string;
  password: string;
  full_name?: string;
  organization_name?: string;
}) {
  if (DEMO_MODE) {
    return persistSession({
      access_token: 'demo-token',
      refresh_token: 'demo-refresh-token',
      user: {
        ...demoUser,
        email: input.email,
        full_name: input.full_name || 'Usuário Demo',
      },
    });
  }

  const { data } = await api.post('/auth/register', input);
  return persistSession(data);
}

export async function me() {
  if (DEMO_MODE) return demoUser;

  const { data } = await api.get('/auth/me');
  return data;
}

export async function logoutRemote() {
  if (!DEMO_MODE) {
    try {
      await api.post('/auth/logout');
    } catch {}
  }

  logout();
}

export function logout() {
  localStorage.removeItem('financeos_token');
  localStorage.removeItem('financeos_refresh_token');
  localStorage.removeItem('financeos_user');
}

async function refreshToken() {
  if (DEMO_MODE) return 'demo-token';

  const refresh_token = localStorage.getItem('financeos_refresh_token');
  if (!refresh_token) return null;

  const { data } = await axios.post(`${baseURL}/auth/refresh`, { refresh_token });
  persistSession(data);

  return data.access_token as string;
}

let refreshing: Promise<string | null> | null = null;

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('financeos_token');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  if (!DEMO_MODE) {
    return config;
  }

  const rawUrl = String(config.url || '');
  const cleanUrl = rawUrl.replace(/^\/api/, '');
  const normalizedUrl = `/api${cleanUrl}`;

  const mutationData = persistDemoMutation(config);

  if (mutationData !== null) {
    config.adapter = async () => ({
      data: mutationData,
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });

    return config;
  }

  const data = demoResponses[rawUrl] ?? demoResponses[normalizedUrl] ?? demoResponses[cleanUrl];

  console.log('[DEMO API]', {
    method: config.method,
    rawUrl,
    cleanUrl,
    normalizedUrl,
    found: data !== undefined,
  });

  if (data !== undefined) {
    config.adapter = async () => ({
      data,
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    });
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (DEMO_MODE) {
      return Promise.reject(error);
    }

    const original = error.config || {};
    const status = error.response?.status;

    const isAuthCall =
      String(original.url || '').includes('/auth/login') ||
      String(original.url || '').includes('/auth/register') ||
      String(original.url || '').includes('/auth/refresh');

    if (status === 401 && !original._retry && !isAuthCall) {
      original._retry = true;

      refreshing =
        refreshing ||
        refreshToken().finally(() => {
          refreshing = null;
        });

      const token = await refreshing;

      if (token) {
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }

      logout();
      window.location.href = '/login';
    }

    return Promise.reject(error);
  },
);
