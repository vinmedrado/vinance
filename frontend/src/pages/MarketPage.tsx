import { useState, type FormEvent } from 'react';
import { Button, Card, EmptyState, LoadingState, MarketTable, SectionHeader, Tabs } from '../components';
import { useFundamentals, useMacroIndicators, useRendaFixa } from '../features/market/hooks/useMarket';
import type { FundamentalItem, MacroIndicator, RendaFixaItem } from '../features/market/types/market.types';
import { formatCompactNumber, formatCurrency, formatDate, formatDecimal, formatFinancialRate, formatInteger, formatPercent } from '../utils/formatters';
import { localDateInputValue } from '../utils/localDate';

type FundamentalsKind = 'fii' | 'acoes' | 'etf' | 'bdr' | 'cripto';

const classNames: Record<FundamentalsKind, string> = {
  fii: 'fundos imobiliários', acoes: 'ações', etf: 'ETFs', bdr: 'BDRs', cripto: 'criptoativos',
};

function pick(item: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = item[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return null;
}

function text(item: Record<string, unknown>, keys: string[]) {
  const value = pick(item, keys);
  return value === null ? '—' : String(value);
}

function numeric(item: Record<string, unknown>, keys: string[]) {
  const value = pick(item, keys);
  return typeof value === 'number' || typeof value === 'string' ? value : null;
}

function sourceName(value: unknown) {
  const key = String(value ?? '').toLowerCase();
  return ({ bcb: 'Banco Central', coingecko: 'CoinGecko', investidor10: 'Investidor10', tesouro_transparente: 'Tesouro Transparente' } as Record<string, string>)[key]
    ?? (value ? String(value) : '—');
}

function formattedDate(item: Record<string, unknown>) {
  const value = pick(item, ['reference_date', 'date', 'market_date', 'updated_at', 'coletado_em']);
  return formatDate(value === null ? null : String(value));
}

function fundamentalColumns(kind: FundamentalsKind) {
  const identity = { key: 'ticker', label: 'Ativo', render: (item: FundamentalItem) => text(item, ['ticker', 'symbol', 'nome', 'name']) };
  const source = { key: 'source', label: 'Fonte', render: (item: FundamentalItem) => sourceName(item.source) };
  const date = { key: 'reference_date', label: 'Data-base', render: formattedDate };

  if (kind === 'cripto') return [
    identity,
    { key: 'price_brl', label: 'Preço', render: (item: FundamentalItem) => formatCurrency(numeric(item, ['price_brl'])) },
    { key: 'price_change_24h_pct', label: 'Variação 24h', render: (item: FundamentalItem) => formatPercent(numeric(item, ['price_change_24h_pct'])) },
    { key: 'market_cap_usd', label: 'Valor de mercado (US$)', render: (item: FundamentalItem) => {
      const value = formatCompactNumber(numeric(item, ['market_cap_usd']));
      return value === '—' ? value : `US$ ${value}`;
    } },
    { key: 'volume_24h_usd', label: 'Volume 24h (US$)', render: (item: FundamentalItem) => {
      const value = formatCompactNumber(numeric(item, ['volume_24h_usd']));
      return value === '—' ? value : `US$ ${value}`;
    } },
    source,
    date,
  ];

  const price = { key: 'price', label: 'Preço', render: (item: FundamentalItem) => formatCurrency(numeric(item, ['price', 'cotacao', 'preco_atual'])) };
  const dividendYield = { key: 'dy_12m', label: 'Dividend yield (12m)', render: (item: FundamentalItem) => formatPercent(numeric(item, ['dy_12m', 'dividend_yield'])) };
  const liquidity = { key: 'liquidez', label: 'Liquidez diária', render: (item: FundamentalItem) => formatCompactNumber(numeric(item, ['liquidez_diaria', 'volume_medio_diario', 'liquidez'])) };
  if (kind === 'fii') return [identity, price, dividendYield, { key: 'p_vp', label: 'P/VP', render: (item: FundamentalItem) => formatDecimal(numeric(item, ['p_vp', 'pvp'])) }, liquidity, source, date];
  if (kind === 'acoes') return [identity, price, { key: 'pl', label: 'P/L', render: (item: FundamentalItem) => formatDecimal(numeric(item, ['pl', 'p_l'])) }, dividendYield, liquidity, source, date];
  if (kind === 'etf') return [identity, price, { key: 'return_12m', label: 'Retorno (12m)', render: (item: FundamentalItem) => formatPercent(numeric(item, ['retorno_12m', 'return_12m'])) }, liquidity, source, date];
  return [
    identity,
    price,
    dividendYield,
    { key: 'volume_medio_diario_brl', label: 'Volume médio diário', render: (item: FundamentalItem) => formatCompactNumber(numeric(item, ['volume_medio_diario_brl'])) },
    source,
    date,
  ];
}

function FundamentalsList({ kind }: { kind: FundamentalsKind }) {
  const pageSize = 20;
  const [offset, setOffset] = useState(0);
  const [draftSearch, setDraftSearch] = useState('');
  const [search, setSearch] = useState('');
  const query = useFundamentals(kind, { limit: pageSize, offset, search });
  const className = classNames[kind];
  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + items.length, total);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setOffset(0);
    setSearch(draftSearch.trim());
  }

  function clearSearch() {
    setDraftSearch('');
    setSearch('');
    setOffset(0);
  }

  return <div className="vn-market-browser" aria-busy={query.isFetching}>
    <form className="vn-market-toolbar" role="search" onSubmit={submitSearch}>
      <label className="vn-sr-only" htmlFor={`market-search-${kind}`}>Buscar {className}</label>
      <input
        id={`market-search-${kind}`}
        className="vn-input"
        type="search"
        value={draftSearch}
        onChange={(event) => setDraftSearch(event.target.value)}
        placeholder="Buscar por ticker ou nome"
        maxLength={120}
      />
      <Button type="submit" variant="secondary">Buscar</Button>
      {search && <Button type="button" variant="ghost" onClick={clearSearch}>Limpar</Button>}
    </form>

    {query.isLoading ? <LoadingState label={`Carregando ${className}...`} />
      : query.error ? <EmptyState title="Consulta temporariamente indisponível" description={`Não foi possível consultar ${className}. Tente novamente em instantes.`} />
        : <>
          <div className="vn-market-result-meta" aria-live="polite">
            <span>{total === 0 ? 'Nenhum ativo' : `${formatInteger(first)}–${formatInteger(last)} de ${formatInteger(total)} ativos`}</span>
            {search && <small>Busca: “{search}”</small>}
          </div>
          <MarketTable
            items={items}
            ariaLabel={`Dados de ${className}`}
            primaryKey="ticker"
            secondaryKey={kind === 'cripto' ? 'price_brl' : 'price'}
            getRowKey={(item, index) => String(item.id ?? item.ticker ?? item.coin_id ?? index)}
            emptyTitle={search ? 'Nenhum ativo encontrado' : 'Dados ainda não disponíveis'}
            emptyDescription={search
              ? `Nenhum ativo do snapshot atual corresponde a “${search}”.`
              : `A fonte configurada para ${className} não retornou registros reais. Nenhum dado fictício foi exibido.`}
            columns={fundamentalColumns(kind)}
          />
          {total > 0 && <nav className="vn-market-pagination" aria-label={`Paginação de ${className}`}>
            <Button
              type="button"
              variant="ghost"
              disabled={offset === 0 || query.isFetching}
              onClick={() => setOffset((current) => Math.max(0, current - pageSize))}
            >Anterior</Button>
            <Button
              type="button"
              variant="ghost"
              disabled={offset + items.length >= total || query.isFetching}
              onClick={() => setOffset((current) => current + pageSize)}
            >Próxima</Button>
          </nav>}
        </>}
  </div>;
}

function latestMacroItems(items: MacroIndicator[]) {
  const latest = new Map<string, MacroIndicator>();
  for (const item of items) {
    const raw = item as Record<string, unknown>;
    const key = item.code ?? item.name ?? String(item.id ?? 'indicador');
    const current = latest.get(key);
    const date = String(item.reference_date ?? raw.date ?? '');
    const currentRaw = current as Record<string, unknown> | undefined;
    const currentDate = String(current?.reference_date ?? currentRaw?.date ?? '');
    if (!current || date > currentDate) latest.set(key, item);
  }
  return [...latest.values()].sort((a, b) => String(a.name ?? a.code).localeCompare(String(b.name ?? b.code), 'pt-BR'));
}

function macroValue(item: MacroIndicator) {
  const percentageCodes = new Set(['CDI', 'SELIC', 'IPCA', 'IGPM', 'INPC']);
  return percentageCodes.has(String(item.code).toUpperCase()) ? formatPercent(item.value) : formatDecimal(item.value, { maximumFractionDigits: 4 });
}

function macroReading(item: MacroIndicator) {
  const raw = item as Record<string, unknown>;
  const referenceDate = String(item.reference_date ?? raw.date ?? '');
  const isFutureReference = /^\d{4}-\d{2}-\d{2}$/.test(referenceDate) && referenceDate > localDateInputValue();
  const code = String(item.code ?? '').toUpperCase();
  const source = String(item.source ?? '').toLowerCase();

  if (isFutureReference && code === 'SELIC' && source === 'bcb') {
    return 'Meta Selic vigente. A data indica o período de referência do Banco Central.';
  }
  if (isFutureReference) return 'Referência futura; não é dado realizado';
  if (code === 'SELIC') return 'Meta oficial do Copom';
  return 'Observado';
}

function fixedIncomeRate(item: RendaFixaItem) {
  // The canonical fixed-income engine evaluates the purchase rate.  The
  // historical `taxa_total_equiv` field is the redemption/reference side of
  // the Tesouro dataset and must not be presented as the investor's entry
  // rate when the source provides both values.
  const rate = numeric(item, ['purchase_rate', 'taxa_juros', 'taxa_total_equiv', 'taxa', 'yield']);
  const formatted = formatFinancialRate(rate);
  const indexer = text(item, ['indexador']);
  if (formatted === '—') return formatted;
  if (indexer === '—' || indexer === 'PREFIXED') return formatted;
  return `${indexer} + ${formatted}`;
}

function fixedIncomeLiquidity(item: RendaFixaItem) {
  if (String(pick(item, ['liquidity_type']) ?? '') === 'DAILY_REPURCHASE') return 'Liquidez diária';
  const days = numeric(item, ['liquidez_dias', 'liquidity_days']);
  return days === null ? 'Não informada' : `${formatDecimal(days, { maximumFractionDigits: 0 })} dia(s)`;
}

export function MarketPage() {
  const macro = useMacroIndicators();
  const rendaFixa = useRendaFixa();
  const macroItems = latestMacroItems(macro.data?.items ?? []);

  return <section className="vn-page">
    <SectionHeader eyebrow="Mercado" title="Mercado e indicadores" description="Dados reais das fontes integradas, com data-base e sem projeção de retorno." />
    <div className="vn-grid vn-grid--two">
      <Card title="Indicadores macroeconômicos" description="Último valor disponível de cada indicador. Na Selic, a data informa o período de referência da série oficial do Banco Central.">
        {macro.isLoading ? <LoadingState label="Carregando indicadores..." /> : macro.error ? <EmptyState title="Indicadores indisponíveis" description="Não foi possível consultar os indicadores neste momento." /> : <MarketTable
          items={macroItems} ariaLabel="Indicadores macroeconômicos" primaryKey="name" secondaryKey="value"
          getRowKey={(item, index) => String(item.code ?? item.id ?? index)}
          emptyTitle="Dados ainda não disponíveis" emptyDescription="A fonte de indicadores não retornou observações."
          columns={[
            { key: 'name', label: 'Indicador', render: (item) => text(item, ['name', 'code']) },
            { key: 'value', label: 'Valor', render: macroValue },
            { key: 'reference_date', label: 'Data-base', render: formattedDate },
            { key: 'reading', label: 'Leitura', render: macroReading },
            { key: 'source', label: 'Fonte', render: (item) => sourceName(item.source) },
          ]}
        />}
      </Card>
      <Card title="Renda fixa" description="Títulos públicos disponíveis na fonte oficial integrada; taxas são referências da data-base, não promessa de retorno.">
        {rendaFixa.isLoading ? <LoadingState label="Carregando renda fixa..." /> : rendaFixa.error ? <EmptyState title="Renda fixa indisponível" description="Não foi possível consultar os títulos neste momento." /> : <MarketTable
          items={rendaFixa.data?.items.slice(0, 12) ?? []} ariaLabel="Produtos de renda fixa" primaryKey="nome" secondaryKey="purchase_rate"
          getRowKey={(item, index) => String(item.source_product_id ?? item.id ?? index)}
          emptyTitle="Dados ainda não disponíveis" emptyDescription="A fonte oficial de títulos não retornou produtos."
          columns={[
            { key: 'nome', label: 'Produto', render: (item) => text(item, ['nome', 'name', 'ticker']) },
            { key: 'purchase_rate', label: 'Taxa de referência', render: fixedIncomeRate },
            { key: 'investimento_minimo', label: 'Aporte mínimo', render: (item) => formatCurrency(numeric(item, ['investimento_minimo', 'minimum_investment'])) },
            { key: 'liquidez_dias', label: 'Liquidez', render: fixedIncomeLiquidity },
            { key: 'vencimento', label: 'Vencimento', render: (item) => formatDate(String(pick(item, ['vencimento', 'maturity_date']) ?? '')) },
            { key: 'source', label: 'Fonte', render: (item) => sourceName(item.source) },
          ]}
        />}
      </Card>
    </div>
    <div className="vn-section-gap"><Tabs tabs={[
      { id: 'fii', label: 'FIIs', content: <FundamentalsList kind="fii" /> },
      { id: 'acoes', label: 'Ações', content: <FundamentalsList kind="acoes" /> },
      { id: 'etf', label: 'ETFs', content: <FundamentalsList kind="etf" /> },
      { id: 'bdr', label: 'BDRs', content: <FundamentalsList kind="bdr" /> },
      { id: 'cripto', label: 'Cripto', content: <FundamentalsList kind="cripto" /> },
    ]} /></div>
  </section>;
}
