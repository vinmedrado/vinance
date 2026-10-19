import { api } from '../../../services/api';
import type { FundamentalItem, ListResponse, MacroIndicator, RendaFixaItem } from '../types/market.types';

export async function getMacro() { const { data } = await api.get<ListResponse<MacroIndicator>>('/market/macro'); return data; }
export async function getRendaFixa() { const { data } = await api.get<ListResponse<RendaFixaItem>>('/market/renda-fixa'); return data; }

export type FundamentalsQuery = {
  limit?: number;
  offset?: number;
  search?: string;
};

export async function getFundamentals(
  kind: 'fii' | 'acoes' | 'etf' | 'bdr' | 'cripto',
  query: FundamentalsQuery = {},
) {
  const search = query.search?.trim();
  const { data } = await api.get<ListResponse<FundamentalItem>>(`/market/fundamentals/${kind}`, {
    params: {
      latest: true,
      limit: query.limit ?? 20,
      offset: query.offset ?? 0,
      ...(search ? { search } : {}),
    },
  });
  return data;
}
