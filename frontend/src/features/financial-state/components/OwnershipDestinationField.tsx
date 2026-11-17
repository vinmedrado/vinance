import { useId } from 'react';
import { LockKeyhole, UsersRound } from 'lucide-react';
import type { Household } from '../../household/types/household.types';

export function OwnershipDestinationField({
  households,
  value,
  suggestedHouseholdId,
  onChange,
  disabled = false,
  name,
}: {
  households: Household[];
  value: number | null;
  suggestedHouseholdId?: number | null;
  onChange: (householdId: number) => void;
  disabled?: boolean;
  name?: string;
}) {
  const generatedName = useId();
  const groupName = name ?? `financial-destination-${generatedName}`;
  const active = households.filter((household) => household.status === 'ACTIVE');
  return (
    <fieldset className="vn-destination-field" disabled={disabled}>
      <legend>Onde deseja registrar?</legend>
      <p>Escolha quem poderá visualizar este lançamento.</p>
      <div className="vn-destination-field__options">
        {active.map((household) => {
          const personal = household.household_type === 'PERSONAL';
          const Icon = personal ? LockKeyhole : UsersRound;
          const checked = value === household.id;
          return (
            <label key={household.id} className={checked ? 'is-selected' : undefined}>
              <input
                type="radio"
                name={groupName}
                value={household.id}
                checked={checked}
                onChange={() => onChange(household.id)}
                required
              />
              <Icon size={19} aria-hidden="true" />
              <span>
                <strong>{personal ? 'Minhas finanças' : 'Finanças do casal'}</strong>
                <small>
                  {personal
                    ? 'Informação particular, visível somente para você.'
                    : `Compartilhada com os integrantes autorizados${household.name ? ` de ${household.name}` : ''}.`}
                </small>
                {household.id === suggestedHouseholdId && <em>Contexto atual</em>}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
