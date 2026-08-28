import { api } from '../../../services/api';
import type { AdvisorChatRequest, AdvisorChatResponse } from '../types/advisor.types';

export async function sendAdvisorMessage(payload: AdvisorChatRequest) {
  const { data } = await api.post<AdvisorChatResponse>('/advisor/chat', payload);
  return data;
}
