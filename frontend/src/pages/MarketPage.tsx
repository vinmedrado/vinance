import { Card, EmptyState, LoadingState, MarketTable, SectionHeader, Tabs } from '../components';
import { useFundamentals, useMacroIndicators, useRendaFixa } from '../features/market/hooks/useMarket';
import type { ApiErrorShape } from '../services/api';

function valueOf(item: Record<string, unknown>, keys: string[]) {
  for (const key of keys) if (item[key] !== undefined && item[key] !== null && item[key] !== '') return String(item[key]);
  return '—';
}

function FundamentalsList({ kind }: { kind: 'fii' | 'acoes' | 'etf' | 'bdr' | 'cripto' }) {
  const query = useFundamentals(kind);
  const error = query.error as ApiErrorShape | null;
  if (query.isLoading) return <LoadingState label={`Carregando fundamentos de ${kind}...`} />;
  if (error) return <EmptyState title="Fundamentos indisponíveis" description={error.message} />;
  return <MarketTable items={query.data?.items.slice(0, 12) ?? []} emptyTitle="Sem fundamentos" emptyDescription="O backend não retornou registros para esta classe." columns={[
    { key: 'ticker', label: 'Ativo', render: (item) => valueOf(item, ['ticker', 'symbol', 'nome', 'name']) },
    { key: 'dy_12m', label: 'DY / retorno', render: (item) => valueOf(item, ['dy_12m', 'retorno_12m', 'price_change_30d_pct']) },
    { key: 'liquidez', label: 'Liquidez', render: (item) => valueOf(item, ['liquidez_diaria', 'volume_medio_diario', 'volume_24h_usd', 'liquidez']) },
    { key: 'source', label: 'Fonte', render: (item) => valueOf(item, ['source']) },
    { key: 'reference_date', label: 'Data', render: (item) => valueOf(item, ['reference_date', 'date', 'updated_at']) },
  ]} />;
}

export function MarketPage() {
  const macro = useMacroIndicators();
  const rendaFixa = useRendaFixa();
  const macroError = macro.error as ApiErrorShape | null;
  const rendaError = rendaFixa.error as ApiErrorShape | null;

  return <section className="vn-page">
    <SectionHeader eyebrow="Mercado" title="Fundamentos por classe." description="Leitura organizada dos endpoints reais de mercado, sem provider novo e sem scraping." />
    <div className="vn-grid vn-grid--two">
      <Card title="Indicadores macro" description="Resumo de indicadores macroeconômicos disponíveis no backend.">
        {macro.isLoading ? <LoadingState label="Carregando macro..." /> : macroError ? <EmptyState title="Macro indisponível" description={macroError.message} /> : <MarketTable items={macro.data?.items.slice(0, 8) ?? []} emptyTitle="Sem macro" emptyDescription="Nenhum indicador macro retornado." columns={[
          { key: 'name', label: 'Indicador', render: (item) => valueOf(item, ['name', 'code']) },
          { key: 'value', label: 'Valor' },
          { key: 'reference_date', label: 'Data' },
          { key: 'source', label: 'Fonte' },
        ]} />}
      </Card>
      <Card title="Renda fixa" description="Produtos de renda fixa disponíveis para leitura educacional.">
        {rendaFixa.isLoading ? <LoadingState label="Carregando renda fixa..." /> : rendaError ? <EmptyState title="Renda fixa indisponível" description={rendaError.message} /> : <MarketTable items={rendaFixa.data?.items.slice(0, 8) ?? []} emptyTitle="Sem renda fixa" emptyDescription="Nenhum produto retornado." columns={[
          { key: 'nome', label: 'Produto', render: (item) => valueOf(item, ['nome', 'name', 'ticker']) },
          { key: 'taxa_total_equiv', label: 'Taxa', render: (item) => valueOf(item, ['taxa_total_equiv', 'taxa', 'yield']) },
          { key: 'liquidez_dias', label: 'Liquidez' },
          { key: 'garantia_fgc', label: 'FGC' },
        ]} />}
      </Card>
    </div>
    <div className="vn-section-gap"><Tabs tabs={[{ id: 'fii', label: 'FIIs', content: <FundamentalsList kind="fii" /> }, { id: 'acoes', label: 'Ações', content: <FundamentalsList kind="acoes" /> }, { id: 'etf', label: 'ETFs', content: <FundamentalsList kind="etf" /> }, { id: 'bdr', label: 'BDRs', content: <FundamentalsList kind="bdr" /> }, { id: 'cripto', label: 'Cripto', content: <FundamentalsList kind="cripto" /> }]} /></div>
  </section>;
}
