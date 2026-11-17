import { useEffect, useState } from 'react';
import { Button } from '../../../components';
import { useCurrentUser } from '../../auth/hooks/useAuth';
import { useFinancialContext } from '../context/FinancialContextProvider';

export function SharedFinanceIntro() {
  const { data: user } = useCurrentUser();
  const context = useFinancialContext();
  const household = context.activeHousehold;
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    if (!user?.id || household?.household_type !== 'SHARED') {
      setDismissed(true);
      return;
    }
    setDismissed(
      window.localStorage.getItem(`vinance:shared-finance-intro:${user.id}:${household.id}`) === 'dismissed',
    );
  }, [household, user?.id]);

  if (dismissed || !user?.id || household?.household_type !== 'SHARED') return null;

  function dismiss() {
    window.localStorage.setItem(
      `vinance:shared-finance-intro:${user?.id}:${household?.id}`,
      'dismissed',
    );
    setDismissed(true);
  }

  return (
    <aside className="vn-context-guidance" aria-label="Orientação sobre as Finanças do casal">
      <div>
        <strong>Este é o espaço financeiro compartilhado.</strong>
        <p>Os lançamentos daqui ajudam no planejamento do casal. Suas finanças pessoais continuam privadas.</p>
      </div>
      <Button variant="ghost" onClick={dismiss}>Entendi</Button>
    </aside>
  );
}
