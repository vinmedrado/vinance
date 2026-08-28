export type AssetClass = 'renda_fixa' | 'fii' | 'acoes' | 'etf' | 'bdr' | 'cripto';
export type AllocationItem = { asset_class: AssetClass; percentage: string; amount: string };
export type AssetScore = { ticker: string; name?: string | null; asset_class: AssetClass; score: number; reasons: string[]; missing_fields: string[]; methodology: string };
export type RecommendationClass = { asset_class: AssetClass; allocation_percentage: string; allocation_amount: string; assets: AssetScore[]; message?: string | null };
export type RecommendationResponse = { financial_score: number; investment_capacity: string; adjusted_risk_profile: string; allocation: AllocationItem[]; recommendations_by_class: RecommendationClass[]; warnings: string[]; methodology: string[] };
