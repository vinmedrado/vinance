from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.financing.schemas import FinancingSimulationRequest

DecisionClass = Literal["seguro", "moderado", "arriscado"]


class FinancialSummaryResponse(BaseModel):
    renda_total: float
    despesas_totais: float
    despesas_pendentes: float
    despesas_pagas: float
    saldo_mensal: float
    saldo_disponivel: float
    capacidade_pagamento: float
    comprometimento_atual_pct: float | None
    fonte: str
    core: dict


class FinancialCapacityResponse(FinancialSummaryResponse):
    capacidade_segura: float
    capacidade_moderada: float
    limite_maximo_recomendado: float
    recomendacao_textual: str


class FinancialAnalysisRequest(BaseModel):
    financing: FinancingSimulationRequest
    renda_mensal: float | None = Field(default=None, gt=0)
    despesas_mensais: float | None = Field(default=None, ge=0)
    saldo_disponivel: float | None = Field(default=None, ge=0)
    usar_dados_core: bool = True

    @model_validator(mode="after")
    def validate_manual_context(self) -> "FinancialAnalysisRequest":
        if not self.usar_dados_core and self.renda_mensal is None:
            raise ValueError("renda_mensal é obrigatória quando usar_dados_core=false")
        return self


class FinancialAnalysisResponse(BaseModel):
    renda_total: float
    despesas_totais: float
    saldo_mensal: float
    saldo_disponivel: float
    capacidade_pagamento: float
    parcela_simulada: float
    percentual_comprometimento: float | None
    comprometimento_total_pct: float | None
    classificacao: DecisionClass
    pode_financiar: bool
    margem_apos_parcela: float
    margem_apos_parcela_pct: float | None
    recomendacao_textual: str
    motivos: list[str]
    como_melhorar: list[str]
    cenarios: list[dict]
    melhor_cenario: dict | None
    financing_result: dict
    core_summary: dict

RiskProfile = Literal["conservador", "moderado", "agressivo"]


class InvestmentAdviceRequest(BaseModel):
    renda_mensal: float | None = Field(default=None, gt=0)
    despesas_mensais: float | None = Field(default=None, ge=0)
    reserva_emergencia: float = Field(default=0.0, ge=0)
    capital_disponivel: float = Field(default=0.0, ge=0)
    capacidade_investimento_mensal: float | None = Field(default=None, ge=0)
    perfil_risco: RiskProfile = "conservador"
    parcela_divida_mensal: float = Field(default=0.0, ge=0)
    usar_dados_core: bool = True


class InvestmentAdviceResponse(BaseModel):
    perfil_risco: RiskProfile
    situacao: str
    recomendacao: str
    titulo: str
    renda_mensal: float
    despesas_mensais: float
    saldo_mensal: float
    capacidade_investimento_mensal: float
    reserva_emergencia_atual: float
    reserva_emergencia_meta: float
    reserva_emergencia_gap: float
    meses_reserva: float
    alocacao_sugerida: list[dict]
    fatores: list[str]
    proximos_passos: list[str]
    mensagem: str
    disclaimer: str


class FinancialDashboardResponse(BaseModel):
    resumo: FinancialSummaryResponse
    capacidade: FinancialCapacityResponse
    saude_financeira: dict
    investimento_base: InvestmentAdviceResponse
    proximos_passos: list[str]


class FinancialDecisionHistoryResponse(BaseModel):
    history: list[dict]

class UserProfileUpsertRequest(BaseModel):
    nome: str | None = None
    perfil_risco: RiskProfile = "conservador"
    renda_mensal: float = Field(default=0.0, ge=0)
    despesas_mensais: float = Field(default=0.0, ge=0)
    reserva_emergencia: float = Field(default=0.0, ge=0)
    reserva_meses_alvo: float = Field(default=6.0, ge=1, le=24)
    meta_investimento_mensal: float = Field(default=0.0, ge=0)
    meta_economia_mensal: float = Field(default=0.0, ge=0)
    objetivo_principal: str | None = None
    onboarding_completed: bool = False


class UserProfileResponse(UserProfileUpsertRequest):
    id: int
    user_id: int


class GoalRequest(BaseModel):
    nome: str
    tipo: str = "geral"
    valor_alvo: float = Field(default=0.0, ge=0)
    valor_atual: float = Field(default=0.0, ge=0)
    prazo: str | None = None
    prioridade: Literal["baixa", "media", "alta"] = "media"
    status: Literal["ativo", "concluido", "pausado"] = "ativo"


class GoalResponse(GoalRequest):
    id: int
    progresso_pct: float


class MonthlyTargetRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    renda_prevista: float = Field(default=0.0, ge=0)
    despesa_limite: float = Field(default=0.0, ge=0)
    economia_meta: float = Field(default=0.0, ge=0)
    investimento_meta: float = Field(default=0.0, ge=0)
    reserva_meta: float = Field(default=0.0, ge=0)
    observacao: str | None = None


class MonthlyTargetResponse(MonthlyTargetRequest):
    id: int
    saldo_planejado: float


class ExecutiveDashboardResponse(BaseModel):
    perfil: dict | None
    resumo: dict
    saude_financeira: dict
    objetivos: list[dict]
    meta_mensal: dict | None
    reserva_emergencia: dict
    evolucao_historica: list[dict]
    relatorio_mensal: dict | None
    proximos_passos: list[str]


class MonthlyReportResponse(BaseModel):
    report: dict


class AdvancedAdvisorRequest(BaseModel):
    """Entrada opcional para o consultor avançado.

    Quando não vier financiamento, o consultor usa perfil + core + metas persistidas.
    Quando vier financiamento, a parcela entra no risco e reduz capacidade de investimento.
    """

    financing: FinancingSimulationRequest | None = None
    investimento_mensal_planejado: float | None = Field(default=None, ge=0)
    usar_dados_core: bool = True


class AdvancedAdvisorResponse(BaseModel):
    decisao: Literal["Não recomendado", "Recomendado com ajustes", "Seguro"]
    classificacao: DecisionClass
    acao_principal_recomendada: str
    diagnostico: str
    explicacao: dict
    motor_prioridade: dict
    projecao_futura: list[dict]
    plano_automatico: dict
    alertas_inteligentes: list[dict]
    integracao_total: dict
