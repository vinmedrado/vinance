from __future__ import annotations

from .config import ValidationConfig
from .validator import ValidationCampaign


def run_validation(config: ValidationConfig | None = None):
    resolved = config or ValidationConfig()
    return ValidationCampaign(resolved).run()


def main() -> int:
    result = run_validation()
    print(f"validation_run_id={result.run_id}")
    print(f"overall_score={result.overall_score:.4f} classification={result.classification}")
    print(f"validated_cases={result.coverage['validated_cases']}")
    print(f"paper_trading_ready={result.readiness['paper_trading_ready']}")
    print(f"paper_trading_continuous_ready={result.readiness['paper_trading_continuous_ready']}")
    print("live_trading_ready=False")
    print(f"reports={result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
