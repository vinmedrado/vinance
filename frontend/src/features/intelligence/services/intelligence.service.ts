import { api } from '../../../services/api';
import type { RecommendationResponse } from '../types/intelligence.types';

export async function getRecommendations(params?: { amount?: number; risk_profile?: string }) {
  const { data } = await api.get<RecommendationResponse>('/intelligence/recommendations', { params });
  return data;
}
