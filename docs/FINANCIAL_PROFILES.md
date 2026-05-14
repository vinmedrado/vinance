# Perfis Financeiros

Tabela principal: `financial_profiles`.

Campos centrais:

- organization_id;
- user_id;
- monthly_income;
- monthly_expenses;
- available_to_invest;
- emergency_reserve_months;
- risk_profile;
- investment_experience;
- financial_goal;
- target_amount;
- target_date;
- preferred_markets;
- liquidity_preference;
- dividend_preference;
- volatility_tolerance;
- investment_horizon;
- monthly_investment_capacity.

Todo perfil pertence a uma organização e a um usuário. As rotas filtram por `organization_id` e usam RBAC.
