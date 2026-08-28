import { Button } from './Button';
import { EmptyState } from './EmptyState';

export function EmptyPortfolioState() {
  return <EmptyState title="Ainda falta contexto financeiro" description="Complete o perfil e cadastre receitas/despesas para o Vinance explicar score, capacidade de aporte e alocação com base real." action={<Button onClick={() => window.location.assign('/financial')}>Completar financeiro</Button>} />;
}
