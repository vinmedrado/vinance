import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import {
  Button,
  EmptyState,
  MetricCard,
  PremiumTable,
  SectionHeader,
  StatusBadge,
  Card,
} from '../components/ui';

const cfg: Record<string, { title: string; desc: string; endpoint: string; eyebrow: string }> = {
  receitas: {
    title: 'Receitas',
    desc: 'Entradas recorrentes e eventuais usadas no orçamento e diagnóstico.',
    endpoint: '/incomes',
    eyebrow: 'Financeiro',
  },
  contas: {
    title: 'Contas',
    desc: 'Contas bancárias conectadas ao fluxo financeiro.',
    endpoint: '/accounts',
    eyebrow: 'Financeiro',
  },
  cartoes: {
    title: 'Cartões',
    desc: 'Limites, vencimentos e despesas por cartão em visual limpo.',
    endpoint: '/cards',
    eyebrow: 'Financeiro',
  },
  metas: {
    title: 'Metas',
    desc: 'Objetivos financeiros conectados à sobra mensal e ao orçamento.',
    endpoint: '/goals',
    eyebrow: 'Planejamento',
  },
  investimentos: {
    title: 'Investimentos',
    desc: 'Planejamento mensal de aportes conectado ao orçamento.',
    endpoint: '/investments',
    eyebrow: 'Investimentos',
  },
  carteira: {
    title: 'Carteira',
    desc: 'Visão de alocação e evolução patrimonial.',
    endpoint: '/portfolio',
    eyebrow: 'Investimentos',
  },
  alertas: {
    title: 'Alertas',
    desc: 'Avisos financeiros e oportunidades importantes.',
    endpoint: '/alerts',
    eyebrow: 'Inteligência',
  },
};

type GenericForm = {
  name: string;
  amount: string;
  status: string;
  description: string;
};

const defaultForm: GenericForm = {
  name: '',
  amount: '',
  status: 'ativo',
  description: '',
};

export default function SimpleCrudPage({ kind }: { kind: string }) {
  const c = cfg[kind];
  const qc = useQueryClient();

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<GenericForm>(defaultForm);
  const [saving, setSaving] = useState(false);

  const { data, isLoading } = useApi<any>([kind], c.endpoint);

  const rows = useMemo(() => {
    if (Array.isArray(data)) return data;
    return data?.alerts || data?.positions || [];
  }, [data]);

  async function refresh() {
    await qc.invalidateQueries({ queryKey: [kind] });
    await qc.refetchQueries({ queryKey: [kind] });
    await qc.invalidateQueries({ queryKey: ['dashboard'] });
  }

  function openCreate() {
    setForm(defaultForm);
    setOpen(true);
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);

    try {
      const payload = {
        name: form.name,
        title: form.name,
        description: form.description,
        amount: Number(form.amount || 0),
        value: Number(form.amount || 0),
        status: form.status || 'ativo',
      };

      await api.post(c.endpoint, payload);
      await refresh();

      setOpen(false);
      setForm(defaultForm);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <SectionHeader
        eyebrow={c.eyebrow}
        title={c.title}
        description={c.desc}
        action={<Button onClick={openCreate}>Novo registro</Button>}
      />

      <div className="metrics-grid">
        <MetricCard label="Registros" value={String(rows.length || 0)} />
        <MetricCard label="Status" value="Ativo" tone="good" />
        <MetricCard label="Integração" value="ERP" />
        <MetricCard label="Experiência" value="Premium" />
      </div>

      {open && (
        <Card>
          <div className="card-title">
            <div>
              <h3>Novo registro em {c.title}</h3>
              <p>Cadastre informações para alimentar o diagnóstico financeiro do Vinance.</p>
            </div>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Fechar
            </Button>
          </div>

          <form className="form" onSubmit={handleSubmit}>
            <label>
              Nome
              <input
                value={form.name}
                onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
                required
                placeholder={`Ex: ${kind === 'contas' ? 'Conta Nubank' : 'Registro principal'}`}
              />
            </label>

            <div className="form-row">
              <label>
                Valor
                <input
                  value={form.amount}
                  onChange={(e) => setForm((s) => ({ ...s, amount: e.target.value }))}
                  type="number"
                  step="0.01"
                  placeholder="0,00"
                />
              </label>

              <label>
                Status
                <select
                  value={form.status}
                  onChange={(e) => setForm((s) => ({ ...s, status: e.target.value }))}
                >
                  <option value="ativo">Ativo</option>
                  <option value="pendente">Pendente</option>
                  <option value="pausado">Pausado</option>
                  <option value="concluido">Concluído</option>
                </select>
              </label>
            </div>

            <label>
              Observações
              <textarea
                value={form.description}
                onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))}
                placeholder="Detalhes úteis para análise futura"
              />
            </label>

            <div className="form-row">
              <Button type="submit" disabled={saving}>
                {saving ? 'Salvando...' : 'Salvar registro'}
              </Button>

              <Button type="button" variant="soft" onClick={() => setOpen(false)}>
                Cancelar
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card>
        <div className="card-title">
          <div>
            <h3>{c.title} cadastrados</h3>
            <p>Visual limpo para usuário comum, mantendo as regras de negócio existentes no backend.</p>
          </div>

          <StatusBadge tone="info">SaaS</StatusBadge>
        </div>

        {isLoading ? (
          <div className="skeleton-line" />
        ) : rows.length ? (
          <PremiumTable>
            <thead>
              <tr>
                <th>Registro</th>
                <th>Valor</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {rows.map((r: any, i: number) => (
                <tr key={r.id || i}>
                  <td>
                    <strong>{r.name || r.nome || r.title || r.description || 'Registro'}</strong>
                    <small>{r.message || r.tipo || r.notes || r.description || 'Sem observações'}</small>
                  </td>

                  <td>{r.amount || r.valor_alvo || r.value || r.price || ''}</td>

                  <td>
                    <StatusBadge tone={r.status || 'success'}>{r.status || 'ativo'}</StatusBadge>
                  </td>
                </tr>
              ))}
            </tbody>
          </PremiumTable>
        ) : (
          <EmptyState
            title={`${c.title} ainda vazio`}
            message="Cadastre dados para desbloquear diagnóstico, orçamento e recomendações personalizadas."
            action={<Button onClick={openCreate}>Adicionar agora</Button>}
          />
        )}
      </Card>
    </div>
  );
}