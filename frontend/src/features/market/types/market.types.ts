export type ListResponse<T> = { items: T[]; total: number; limit?: number; offset?: number };
export type MacroIndicator = { id?: number; code?: string; name?: string; value?: string | number; reference_date?: string; source?: string; created_at?: string; updated_at?: string };
export type FundamentalItem = Record<string, string | number | boolean | null | undefined> & { ticker?: string; name?: string; source?: string };
export type RendaFixaItem = FundamentalItem;
