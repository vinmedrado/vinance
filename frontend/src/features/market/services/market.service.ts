import { api } from '../../../services/api';
import type { FundamentalItem, ListResponse, MacroIndicator, RendaFixaItem } from '../types/market.types';

export async function getMacro() { const { data } = await api.get<ListResponse<MacroIndicator>>('/market/macro'); return data; }
export async function getRendaFixa() { const { data } = await api.get<ListResponse<RendaFixaItem>>('/market/renda-fixa'); return data; }
export async function getFundamentals(kind: 'fii' | 'acoes' | 'etf' | 'bdr' | 'cripto') { const { data } = await api.get<ListResponse<FundamentalItem>>(`/market/fundamentals/${kind}`, { params: { limit: 20 } }); return data; }
