from __future__ import annotations

from .config import ResearchConfig
from .optimizer import ResearchOptimizer


def run_research(config: ResearchConfig | None = None):
    resolved = config or ResearchConfig()
    return ResearchOptimizer(resolved).run()


def main() -> int:
    result = run_research()
    recommendation = result.recommendation
    print(f"research_run_id={result.run_id}")
    print(f"source_backtest_run_id={result.source_run_id}")
    print(
        f"robustness_score={result.robustness['robustness_score']:.4f} "
        f"classification={result.robustness['classification']}"
    )
    print(
        f"recommended_thresholds="
        f"{recommendation['recommended_tp_threshold']}/{recommendation['recommended_sl_threshold']}"
    )
    print(f"ready_for_paper_trading={recommendation['ready_for_paper_trading']}")
    print("ready_for_live_trading=False")
    print(f"reports={result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
