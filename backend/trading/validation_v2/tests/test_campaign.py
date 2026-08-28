from __future__ import annotations

import json

import pytest

from backend.trading.validation_v2.config import ValidationConfig
from backend.trading.validation_v2.validator import ValidationCampaign

from .helpers import validation_fixture


def _config(paths) -> ValidationConfig:
    return ValidationConfig(manifest_path=paths["manifest"], backtesting_output_root=paths["backtests"], research_output_root=paths["research"], output_root=paths["output"])


def test_campaign_consolidates_rankings_readiness_and_strict_json(tmp_path) -> None:
    paths = validation_fixture(tmp_path)
    result = ValidationCampaign(_config(paths)).run()

    assert result.asset_ranking
    assert result.target_ranking
    assert result.model_ranking
    assert result.readiness["live_trading_ready"] is False
    assert len(result.reports) == 10
    for path in result.reports.values():
        json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def test_campaign_is_idempotent(tmp_path) -> None:
    paths = validation_fixture(tmp_path)
    config = _config(paths)
    first = ValidationCampaign(config).run()
    payloads = {name: path.read_text() for name, path in first.reports.items()}
    second = ValidationCampaign(config).run()

    assert first.run_id == second.run_id
    assert payloads == {name: path.read_text() for name, path in second.reports.items()}


def test_paper_only_is_mandatory_and_campaign_never_approves_live(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="PAPER_ONLY"):
        ValidationConfig(paper_only=False)
    paths = validation_fixture(tmp_path)
    result = ValidationCampaign(_config(paths)).run()

    assert result.metadata["performs_trading"] is False
    assert result.metadata["performs_inference"] is False
    assert result.metadata["trains_models"] is False
    assert result.readiness["live_trading_ready"] is False
