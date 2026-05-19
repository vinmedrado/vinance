import { useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Plus, WalletCards } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { Income } from '../types/finance';
import { Button, Card, ChartCard, EmptyState, LoadingState, MetricCard, PremiumTable, SectionHeader, StatusBadge } from '../components/ui';
import { money } from '../utils/format';

export default function Incomes() {
  const qc = useQueryClient();
  const [query, setQuery] = useState('');
  const { data = [], isLoading } = useApi<Income[]>(['incomes'], '/incomes');

  const create = useMutation({
    mutationFn: async (payload: any) => api.post('/incomes', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incomes'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/incomes/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['incomes'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const filtered = useMemo(
    () => data.filter((i) => `${i.description} ${i.status}`.toLowerCase().includes(query.toLowerCase())),
    [data, query],
  );

  const total = data.reduce((s, i) => s + Number(i.amount || 0), 0);
  const received = data.filter((i) => i.status === 'received').reduce((s, i) => s + Number(i.amount || 0), 0);
  const recurring = data.filter((i) => i.recurrence && i.recurrence !== 'none').reduce((s, i) => s + Number(i.amount || 0), 0);

  const evolution = Object.values(data.reduce((acc: any, item) => {
    const d = new Date(item.received_at);
    const month = `${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
    acc[month] = acc[month] || { month, value: 0 };
    acc[month].value += Number(item.amount || 0);
    return acc;
  }, {}));

  return (
    <div className="page">
      <SectionHeader
        eyebrow="Centro financeiro"
        title="Receitas"
        description="Cadastre salários, entradas recorrentes e receitas eventuais. O Vinance recalcula automaticamente orçamento, capacidade de investimento e alocação sugerida."
        action={<Button onClick={() => document.getElementById('income-form')?.scrollIntoView({ behavior: 'smooth' })}><Plus size={18} /> Nova receita</Button>}
      />

      <div className="metrics-grid">
        <MetricCard icon={<WalletCards size={18} />} label="Receita cadastrada" value={total} />
        <MetricCard label="Recebido" value={received} tone="good" />
        <MetricCard label="Recorrente" value={recurring} />
        <MetricCard label="Registros" value={String(data.length)} />
      </div>

      <div className="grid two">
        <Card>
          <h3>Cadastro de receita</h3>
          <p>Ao salvar, o dashboard e a inteligência de alocação são atualizados automaticamente.</p>
          <form id="income-form" className="form" onSubmit={async (e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            await create.mutateAsync({
              description: fd.get('description'),
              amount: Number(fd.get('amount')),
              received_at: fd.get('received_at'),
              recurrence: fd.get('recurrence') || 'none',
              status: fd.get('status') || 'received',
              notes: fd.get('notes'),
            });
            e.currentTarget.reset();
          }}>
            <div className="form-row">
              <label>Valor<input name="amount" type="number" step="0.01" required placeholder="0,00" /></label>
              <label>Data de recebimento<input name="received_at" type="date" required /></label>
            </div>
            <label>Descrição<input name="description" required placeholder="Ex: Salário, freela, comissão" /></label>
            <div className="form-row">
              <label>Recorrência<select name="recurrence"><option value="monthly">Mensal</option><option value="none">Única</option><option value="yearly">Anual</option></select></label>
              <label>Status<select name="status"><option value="received">Recebida</option><option value="pending">Pendente</option></select></label>
            </div>
            <label>Observações<textarea name="notes" placeholder="Detalhes úteis" /></label>
            <Button type="submit" disabled={create.isPending}>{create.isPending ? 'Salvando...' : 'Salvar receita'}</Button>
          </form>
        </Card>

        <ChartCard title="Evolução de receitas" hint="Entradas por mês">
          <ResponsiveContainer width="100%" height={336}>
            <AreaChart data={evolution as any[]}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis tickFormatter={(v) => `R$ ${Number(v) / 1000}k`} />
              <Tooltip formatter={(v) => money(Number(v))} />
              <Area type="monotone" dataKey="value" stroke="currentColor" fill="currentColor" fillOpacity={0.16} strokeWidth={3} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <Card>
        <div className="card-title">
          <div><h3>Receitas cadastradas</h3><p>Esses valores alimentam automaticamente orçamento, dashboard e sugestão de investimento.</p></div>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar receita" />
        </div>
        {isLoading ? <LoadingState title="Buscando receitas..." /> : filtered.length === 0 ? (
          <EmptyState title="Nenhuma receita encontrada" message="Cadastre sua primeira receita para liberar inteligência financeira." action={<Button onClick={() => document.getElementById('income-form')?.scrollIntoView({ behavior: 'smooth' })}>Cadastrar receita</Button>} />
        ) : (
          <PremiumTable>
            <thead><tr><th>Descrição</th><th>Data</th><th>Status</th><th>Valor</th><th>Ações</th></tr></thead>
            <tbody>{filtered.map((i) => <tr key={i.id}><td><strong>{i.description}</strong><small>{i.recurrence || 'none'}</small></td><td>{new Date(i.received_at).toLocaleDateString('pt-BR')}</td><td><StatusBadge tone={i.status}>{i.status}</StatusBadge></td><td>{money(i.amount)}</td><td><Button variant="danger" onClick={() => remove.mutate(i.id)}>Excluir</Button></td></tr>)}</tbody>
          </PremiumTable>
        )}
      </Card>
    </div>
  );
}
