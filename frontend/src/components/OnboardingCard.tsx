import { FormEvent, useEffect, useState } from 'react';
import { Compass } from 'lucide-react';
import { useUpsertProfile } from '../features/financial/hooks/useFinancial';
import type { RiskProfile } from '../features/financial/types/financial.types';
import type { ApiErrorShape } from '../services/api';
import { Card } from './Card';
import { ErrorState } from './ErrorState';
import { MoneyInput } from './MoneyInput';
import { SelectField } from './SelectField';
import { SubmitButton } from './SubmitButton';
import { ToggleField } from './ToggleField';
import { Toast } from './Toast';

const riskOptions = [
  { value: 'conservative', label: 'Conservador' },
  { value: 'moderate', label: 'Moderado' },
  { value: 'aggressive', label: 'Agressivo' },
];

export function OnboardingCard({ onCompleted }: { onCompleted?: () => void }) {
  const upsertProfile = useUpsertProfile();
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({ monthly_salary: '', emergency_reserve: '', risk_profile: 'moderate' as RiskProfile, has_debt_default: false });
  const error = upsertProfile.error as ApiErrorShape | null;

  useEffect(() => {
    if (!saved) return;
    const timer = window.setTimeout(() => setSaved(false), 4200);
    return () => window.clearTimeout(timer);
  }, [saved]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (upsertProfile.isPending) return;
    await upsertProfile.mutateAsync({
      monthly_salary: Number(form.monthly_salary),
      emergency_reserve: Number(form.emergency_reserve),
      risk_profile: form.risk_profile,
      has_debt_default: form.has_debt_default,
    });
    setSaved(true);
    onCompleted?.();
  }

  return (
    <Card className="vn-onboarding-card">
      <div className="vn-onboarding-card__intro">
        <div className="vn-brand__mark"><Compass size={22} /></div>
        <div>
          <span className="vn-kicker">Primeiro diagnóstico</span>
          <h2>Complete seu perfil financeiro inicial.</h2>
          <p>O Vinance precisa desses dados para calcular score, capacidade de aporte, restrições de risco e sugestões educacionais com base real.</p>
        </div>
      </div>
      {error && <ErrorState description={error.message} />}
      {saved && <Toast message="Perfil financeiro salvo. Atualizando seu diagnóstico real..." />}
      <form className="vn-form vn-form--onboarding" onSubmit={submit}>
        <MoneyInput label="Salário mensal" value={form.monthly_salary} onChange={(event) => setForm({ ...form, monthly_salary: event.target.value })} placeholder="Ex.: 5000,00" required />
        <MoneyInput label="Reserva de emergência" value={form.emergency_reserve} onChange={(event) => setForm({ ...form, emergency_reserve: event.target.value })} placeholder="Ex.: 10000,00" required />
        <SelectField label="Perfil de risco" value={form.risk_profile} onChange={(event) => setForm({ ...form, risk_profile: event.target.value as RiskProfile })} options={riskOptions} />
        <ToggleField label="Tenho inadimplência hoje" helper="Isso reduz exposição a risco e prioriza estabilidade no diagnóstico." checked={form.has_debt_default} onChange={(event) => setForm({ ...form, has_debt_default: event.target.checked })} />
        <SubmitButton loading={upsertProfile.isPending}>Criar perfil financeiro</SubmitButton>
      </form>
    </Card>
  );
}
