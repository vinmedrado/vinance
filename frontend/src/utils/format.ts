export const money = (value?: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);
export const pct = (value?: number) => `${(value || 0).toFixed(1)}%`;
