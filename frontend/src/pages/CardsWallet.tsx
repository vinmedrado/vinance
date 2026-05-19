import { useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CreditCard, Plus, ShieldCheck, Trash2, WalletCards } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { api } from '../services/api';
import { Button, Card, EmptyState, LoadingState, MetricCard, SectionHeader, StatusBadge } from '../components/ui';
import { money } from '../utils/format';

type CardItem = {
  id: number;
  name: string;
  brand?: string | null;
  limit_amount: number;
  closing_day?: number | null;
  due_day?: number | null;
  is_active?: boolean;
};

type CardForm = {
  name: string;
  brand: string;
  limit_amount: string;
  closing_day: string;
  due_day: string;
};

const defaultForm: CardForm = {
  name: '',
  brand: '',
  limit_amount: '',
  closing_day: '',
  due_day: '',
};

const brandPresets: Record<string, { label: string; className: string; pattern: string; chip: string }> = {
  nubank: { label: 'Nubank', className: 'card-nubank', pattern: 'NU', chip: '●●●●' },
  itau: { label: 'Itaú', className: 'card-itau', pattern: 'ITAÚ', chip: '●●●●' },
  inter: { label: 'Inter', className: 'card-inter', pattern: 'INTER', chip: '●●●●' },
  c6: { label: 'C6 Bank', className: 'card-c6', pattern: 'C6', chip: '●●●●' },
  xp: { label: 'XP', className: 'card-xp', pattern: 'XP', chip: '●●●●' },
  casasbahia: { label: 'Casas Bahia', className: 'card-casas-bahia', pattern: 'CB', chip: '●●●●' },
  default: { label: 'Vinance Card', className: 'card-default', pattern: 'V', chip: '●●●●' },
};

function normalizeBrand(value?: string | null) {
  const raw = `${value || ''}`.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]/g, '');
  if (raw.includes('nubank') || raw.includes('nu')) return 'nubank';
  if (raw.includes('itau')) return 'itau';
  if (raw.includes('inter')) return 'inter';
  if (raw.includes('c6')) return 'c6';
  if (raw.includes('xp')) return 'xp';
  if (raw.includes('casasbahia') || raw.includes('bahia') || raw.includes('cb')) return 'casasbahia';
  return 'default';
}

function cardLastDigits(id: number) {
  return String(7000 + Number(id || 0)).slice(-4);
}

function CardVisual({ card, selected, onClick }: { card: CardItem; selected?: boolean; onClick?: () => void }) {
  const preset = brandPresets[normalizeBrand(card.brand || card.name)] || brandPresets.default;
  const usage = Math.min(100, Math.max(8, card.limit_amount ? 22 : 8));

  return (
    <button className={`wallet-card ${preset.className} ${selected ? 'selected' : ''}`} onClick={onClick} type="button">
      <span className="wallet-card-glow" />
      <div className="wallet-card-top">
        <div>
          <small>{preset.label}</small>
          <strong>{card.name}</strong>
        </div>
        <span className="wallet-card-brand">{preset.pattern}</span>
      </div>
      <div className="wallet-card-chip"><span /> <em>{preset.chip}</em></div>
      <div className="wallet-card-number">•••• •••• •••• {cardLastDigits(card.id)}</div>
      <div className="wallet-card-bottom">
        <span>Limite</span>
        <strong>{money(Number(card.limit_amount || 0))}</strong>
      </div>
      <div className="wallet-card-progress"><span style={{ width: `${usage}%` }} /></div>
    </button>
  );
}

export default function CardsWallet() {
  const qc = useQueryClient();
  const { data = [], isLoading } = useApi<CardItem[]>(['cartoes'], '/cards');
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CardForm>(defaultForm);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const cards = Array.isArray(data) ? data : [];
  const selected = cards.find((card) => card.id === selectedId) || cards[0];
  const totalLimit = cards.reduce((sum, card) => sum + Number(card.limit_amount || 0), 0);
  const avgLimit = cards.length ? totalLimit / cards.length : 0;

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: ['cartoes'] });
    await qc.refetchQueries({ queryKey: ['cartoes'] });
    await qc.invalidateQueries({ queryKey: ['dashboard'] });
  };

  const createCard = useMutation({
    mutationFn: async () => api.post('/cards', {
      name: form.name,
      brand: form.brand || form.name,
      limit_amount: Number(form.limit_amount || 0),
      closing_day: form.closing_day ? Number(form.closing_day) : null,
      due_day: form.due_day ? Number(form.due_day) : null,
    }),
    onSuccess: async () => {
      await refresh();
      setOpen(false);
      setForm(defaultForm);
    },
  });

  const deleteCard = useMutation({
    mutationFn: async (id: number) => api.delete(`/cards/${id}`),
    onSuccess: async () => {
      setSelectedId(null);
      await refresh();
    },
  });

  const previewCard: CardItem = {
    id: 0,
    name: form.name || 'Novo cartão',
    brand: form.brand || form.name || 'Vinance',
    limit_amount: Number(form.limit_amount || 0),
    closing_day: form.closing_day ? Number(form.closing_day) : null,
    due_day: form.due_day ? Number(form.due_day) : null,
  };

  const brandOptions = useMemo(() => ['Nubank', 'Itaú', 'Inter', 'C6 Bank', 'XP', 'Casas Bahia', 'Outro'], []);

  return (
    <div className="page cards-wallet-page">
      <SectionHeader
        eyebrow="Carteira de crédito"
        title="Cartões"
        description="Cadastre seus cartões como uma carteira visual. Cada cartão ganha identidade própria, limite, fechamento e vencimento para alimentar seu controle financeiro."
        action={<Button onClick={() => setOpen(true)}><Plus size={18} /> Novo cartão</Button>}
      />

      <div className="metrics-grid">
        <MetricCard icon={<WalletCards size={18}/>} label="Cartões ativos" value={String(cards.length)} />
        <MetricCard label="Limite total" value={totalLimit} tone="good" />
        <MetricCard label="Limite médio" value={avgLimit} />
        <MetricCard icon={<ShieldCheck size={18}/>} label="Controle" value="Ativo" hint="Integrado ao ERP" />
      </div>

      {open && (
        <div className="grid two card-create-grid">
          <Card>
            <div className="card-title">
              <div>
                <h3>Adicionar cartão</h3>
                <p>Use o nome real do cartão. O Vinance cria uma versão visual própria inspirada na instituição, sem depender de imagem externa.</p>
              </div>
              <Button variant="ghost" onClick={() => setOpen(false)}>Fechar</Button>
            </div>
            <form className="form" onSubmit={(event) => { event.preventDefault(); createCard.mutate(); }}>
              <label>
                Nome do cartão
                <input value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} required placeholder="Ex: Cartão Casas Bahia" />
              </label>
              <div className="form-row">
                <label>
                  Instituição / Bandeira visual
                  <select value={form.brand} onChange={(e) => setForm((s) => ({ ...s, brand: e.target.value }))}>
                    <option value="">Detectar pelo nome</option>
                    {brandOptions.map((brand) => <option key={brand} value={brand}>{brand}</option>)}
                  </select>
                </label>
                <label>
                  Limite
                  <input value={form.limit_amount} onChange={(e) => setForm((s) => ({ ...s, limit_amount: e.target.value }))} type="number" step="0.01" placeholder="0,00" />
                </label>
              </div>
              <div className="form-row">
                <label>
                  Dia de fechamento
                  <input value={form.closing_day} onChange={(e) => setForm((s) => ({ ...s, closing_day: e.target.value }))} type="number" min="1" max="31" placeholder="Ex: 10" />
                </label>
                <label>
                  Dia de vencimento
                  <input value={form.due_day} onChange={(e) => setForm((s) => ({ ...s, due_day: e.target.value }))} type="number" min="1" max="31" placeholder="Ex: 17" />
                </label>
              </div>
              <div className="form-row">
                <Button type="submit" disabled={createCard.isPending}>{createCard.isPending ? 'Salvando...' : 'Salvar cartão'}</Button>
                <Button type="button" variant="soft" onClick={() => setForm(defaultForm)}>Limpar</Button>
              </div>
            </form>
          </Card>
          <Card className="card-preview-panel">
            <h3>Prévia da carteira</h3>
            <p>O cartão aparece assim na carteira do usuário.</p>
            <CardVisual card={previewCard} />
          </Card>
        </div>
      )}

      {isLoading ? (
        <LoadingState title="Carregando carteira de cartões..." />
      ) : cards.length === 0 ? (
        <EmptyState
          title="Nenhum cartão cadastrado"
          message="Cadastre cartões para controlar limite, vencimentos, fechamento e impacto no orçamento."
          action={<Button onClick={() => setOpen(true)}>Adicionar agora</Button>}
        />
      ) : (
        <div className="grid two cards-wallet-grid">
          <Card className="cards-stack-card">
            <div className="card-title">
              <div>
                <h3>Sua carteira</h3>
                <p>Escolha um cartão para ver detalhes operacionais.</p>
              </div>
              <StatusBadge tone="info">{cards.length} ativo(s)</StatusBadge>
            </div>
            <div className="wallet-card-stack">
              {cards.map((card) => (
                <CardVisual key={card.id} card={card} selected={selected?.id === card.id} onClick={() => setSelectedId(card.id)} />
              ))}
            </div>
          </Card>

          <Card className="card-detail-panel">
            {selected ? (
              <>
                <div className="card-title">
                  <div>
                    <h3>{selected.name}</h3>
                    <p>{selected.brand || 'Cartão cadastrado'} · final {cardLastDigits(selected.id)}</p>
                  </div>
                  <Button variant="danger" onClick={() => deleteCard.mutate(selected.id)}><Trash2 size={16}/> Excluir</Button>
                </div>
                <CardVisual card={selected} selected />
                <div className="card-facts-grid">
                  <div><span>Limite cadastrado</span><strong>{money(Number(selected.limit_amount || 0))}</strong></div>
                  <div><span>Fechamento</span><strong>{selected.closing_day ? `Dia ${selected.closing_day}` : 'Não informado'}</strong></div>
                  <div><span>Vencimento</span><strong>{selected.due_day ? `Dia ${selected.due_day}` : 'Não informado'}</strong></div>
                  <div><span>Status</span><strong>{selected.is_active === false ? 'Inativo' : 'Ativo'}</strong></div>
                </div>
                <div className="callout callout-info">
                  <CreditCard size={18}/>
                  <div>
                    <strong>Próxima evolução</strong>
                    <p>Este cartão poderá receber faturas, parcelas e gastos por categoria para o Vinance prever risco de crédito e limite saudável.</p>
                  </div>
                </div>
              </>
            ) : null}
          </Card>
        </div>
      )}
    </div>
  );
}
