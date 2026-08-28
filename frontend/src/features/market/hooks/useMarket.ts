import { useQuery } from '@tanstack/react-query';
import { getFundamentals, getMacro, getRendaFixa } from '../services/market.service';

export function useMacroIndicators() { return useQuery({ queryKey: ['market', 'macro'], queryFn: getMacro }); }
export function useRendaFixa() { return useQuery({ queryKey: ['market', 'renda-fixa'], queryFn: getRendaFixa }); }
export function useFundamentals(kind: 'fii' | 'acoes' | 'etf' | 'bdr' | 'cripto') { return useQuery({ queryKey: ['market', 'fundamentals', kind], queryFn: () => getFundamentals(kind) }); }
