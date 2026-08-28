export function LoadingState({ label = 'Carregando dados do Vinance...' }: { label?: string }) {
  return <div className="vn-loading" role="status" aria-live="polite"><span /><span /><span /><p>{label}</p></div>;
}
