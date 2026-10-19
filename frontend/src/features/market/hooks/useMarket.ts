import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getFundamentals, getMacro, getRendaFixa, type FundamentalsQuery } from '../services/market.service';

export function useMacroIndicators() { return useQuery({ queryKey: ['market', 'macro'], queryFn: getMacro }); }
export function useRendaFixa() { return useQuery({ queryKey: ['market', 'renda-fixa'], queryFn: getRendaFixa }); }
export function useFundamentals(
  kind: 'fii' | 'acoes' | 'etf' | 'bdr' | 'cripto',
  query: FundamentalsQuery = {},
) {
  return useQuery({
    queryKey: ['market', 'fundamentals', kind, query],
    queryFn: () => getFundamentals(kind, query),
    placeholderData: keepPreviousData,
  });
}
