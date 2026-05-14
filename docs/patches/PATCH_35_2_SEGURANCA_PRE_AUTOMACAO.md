# FinanceOS — PATCH 35.2

Segurança Pré-Automação — Limites, Dependências e Modo Seguro

Incluído:
- novos campos em `automation_rules`:
  - dependencies_json
  - max_runs_per_cycle
  - safe_auto_enabled
  - requires_confirmation
  - automation_group
  - last_blocked_reason
- novos campos em `automation_runs`:
  - confidence_score
  - severity
  - priority
  - skipped_reason
- limite por ciclo:
  - MAX_AUTOMATIONS_PER_CYCLE = 3
- dependências entre automações
- verificação de dependências antes de sugerir/executar
- modo seguro configurável
- confirmação obrigatória para automações pesadas
- cooldown e janela de execução preservados
- UI com:
  - executáveis agora
  - bloqueadas
  - cooldown
  - próximo ciclo
  - modo seguro
  - requer confirmação
  - dependências
  - último bloqueio
- integração com Home
- integração com Saúde do Sistema

Não implementado:
- execução automática sem clique
- scheduler real
- trading
- alteração automática de estratégia

Execução:
streamlit run legacy_streamlit/app.py
