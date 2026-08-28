import { useQuery } from '@tanstack/react-query';
import { getRecommendations } from '../services/intelligence.service';

export function useRecommendations(params?: { amount?: number; risk_profile?: string }) {
  return useQuery({ queryKey: ['intelligence', 'recommendations', params], queryFn: () => getRecommendations(params) });
}
