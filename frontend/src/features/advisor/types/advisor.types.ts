export type AdvisorChatRequest = { message: string };
export type AdvisorWarning = { code: string; message: string };
export type AdvisorContextUsed = { financial: boolean; market: boolean; memory: boolean };
export type AdvisorChatResponse = { response: string; warnings: AdvisorWarning[]; context_used: AdvisorContextUsed };
export type AdvisorMessage = { role: 'user' | 'assistant'; text: string; warnings?: AdvisorWarning[] };
