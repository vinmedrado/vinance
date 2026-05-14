from __future__ import annotations

from app.financial.services.profile_dashboard import _classify


def test_classify_safe_financial_profile():
    classification, diagnosis = _classify(commitment=0.45, reserve_months=6.5, balance=2500, income=10000)
    assert classification == "seguro"
    assert "saudável" in diagnosis


def test_classify_risky_when_no_reserve_and_high_commitment():
    classification, diagnosis = _classify(commitment=0.82, reserve_months=0.5, balance=300, income=6000)
    assert classification == "arriscado"
    assert "pressionado" in diagnosis
