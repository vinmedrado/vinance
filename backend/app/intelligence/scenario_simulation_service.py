from __future__ import annotations
from backend.app.intelligence.schemas import BacktestScenario, ScenarioSimulationOut

class ScenarioSimulationService:
    @staticmethod
    def simulate(*, current_amount: float=0, monthly_contribution: float=0, months: int=120, target_amount: float|None=None) -> ScenarioSimulationOut:
        rates={'pessimista':0.045,'base':0.09,'otimista':0.13,'crise':-0.015,'inflação alta':0.055,'juros altos':0.075,'bull market':0.16,'bear market':0.015}
        scenarios=[]
        for name, annual in rates.items():
            r=(1+annual)**(1/12)-1 if annual>-1 else 0
            value=current_amount
            for _ in range(months): value=max(0,value*(1+r)+monthly_contribution)
            invested=current_amount+monthly_contribution*months
            chance=None if not target_amount else max(1,min(99,50+(value-target_amount)/target_amount*50))
            scenarios.append(BacktestScenario(name=name, estimated_final_amount=round(value,2), estimated_gain=round(max(value-invested,0),2), chance_to_reach_goal_pct=round(chance,2) if chance is not None else None))
        return ScenarioSimulationOut(scenarios=scenarios, impacts={'patrimonio':'varia conforme juros, inflação e risco aceito','meta':'aportes maiores reduzem dependência de retorno','carteira':'cenários ruins testam se a carteira continua adequada'}, user_summary='Cenários mostram caminhos possíveis para planejamento, sem promessa de resultado.')
