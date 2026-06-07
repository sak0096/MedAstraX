from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.explainability.pipeline import run_explainability
from hc_analytics.language.query_cache import load_result
from hc_analytics.language.query_parser import parse_natural_language_query
from hc_analytics.language.summaries import build_grounded_summary
from hc_analytics.modeling.pipeline import run_training


def _sample_feature_row(
    *,
    bene_id: str,
    analytic_year: int,
    inpatient_claims: int,
    total_claims: int,
    total_payment_amt: float,
    next_year_hospitalization: int,
    next_year_high_utilization: int,
    next_year_elevated_cost: int,
) -> dict:
    return {
        "bene_id": bene_id,
        "analytic_year": analytic_year,
        "age": 72,
        "sex": "1",
        "race": "1",
        "state_code": "01",
        "esrd_ind": "0",
        "inpatient_claims": inpatient_claims,
        "outpatient_claims": 2,
        "carrier_claims": 3,
        "snf_claims": 0,
        "dme_claims": 0,
        "hha_claims": 0,
        "hospice_claims": 0,
        "total_claims": total_claims,
        "total_payment_amt": total_payment_amt,
        "inpatient_payment_amt": float(inpatient_claims * 1000),
        "rx_fill_count": 4,
        "rx_unique_drugs": 2,
        "rx_days_supply": 90,
        "distinct_diagnosis_count": 2,
        "has_diabetes": 0,
        "has_chf": int(inpatient_claims > 0),
        "has_copd": 0,
        "has_ckd": 0,
        "has_hypertension": 1,
        "chronic_condition_count": 1,
        "readmission_30d_count": 0,
        "next_year_hospitalization": next_year_hospitalization,
        "next_year_high_utilization": next_year_high_utilization,
        "next_year_elevated_cost": next_year_elevated_cost,
    }


@pytest.fixture()
def language_settings(tmp_path: Path) -> Settings:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)

    rows = []
    for year in (2019, 2020, 2021, 2022, 2023):
        for index, bene_id in enumerate(("B1", "B2", "B3", "B4")):
            rows.append(
                _sample_feature_row(
                    bene_id=bene_id,
                    analytic_year=year,
                    inpatient_claims=1 if (index + year) % 2 == 0 else 0,
                    total_claims=5 + index,
                    total_payment_amt=1000.0 + (index * 250) + year,
                    next_year_hospitalization=int((index + year) % 3 == 0),
                    next_year_high_utilization=int(index >= 2),
                    next_year_elevated_cost=int(index % 2 == 1),
                )
            )

    features = pd.DataFrame(rows)
    features.loc[features["bene_id"] == "B2", "has_diabetes"] = 1
    features.to_parquet(processed / "feature_store.parquet", index=False)
    return Settings(
        repo_root=tmp_path,
        data_processed_dir=Path("data/processed"),
        artifacts_dir=Path("artifacts"),
    )


def _patch_settings(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr("hc_analytics.api.app.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.language.provider.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.api.data_access.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.api.routes.language.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.api.routes.explanations.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.language.query_cache.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.explainability.pipeline.get_settings", lambda: settings)


def test_parse_natural_language_query_detects_sort_and_limit() -> None:
    interpreted = parse_natural_language_query("show top 10 hospitalization risk patients")
    assert interpreted.action == "list_beneficiaries"
    assert interpreted.parameters["sort_by"] == "hospitalization_risk"
    assert interpreted.parameters["limit"] == 10
    assert interpreted.requires_confirmation is True


def test_parse_natural_language_query_detects_chronic_filter() -> None:
    interpreted = parse_natural_language_query("patients with diabetes and high cost")
    assert interpreted.parameters["chronic_filter"] == "has_diabetes"
    assert interpreted.parameters["sort_by"] == "elevated_cost_risk"


def test_build_grounded_summary_uses_bundle_claims(language_settings: Settings) -> None:
    run_training(language_settings, test_year_count=2)
    run_explainability(language_settings, top_k=3, max_rows=8)
    from hc_analytics.explainability.pipeline import load_cached_bundle

    bundle = load_cached_bundle("B1", 2019, settings=language_settings)
    assert bundle is not None
    summary = build_grounded_summary(bundle)
    assert summary.bene_id == "B1"
    assert summary.grounded.fallback is None
    assert len(summary.grounded.claims) > 0
    assert "B1" in summary.narrative


def test_language_api_interpret_confirm_execute(language_settings: Settings, monkeypatch) -> None:
    run_training(language_settings, test_year_count=2)
    run_explainability(language_settings, top_k=3, max_rows=8)
    _patch_settings(monkeypatch, language_settings)

    client = TestClient(app)
    meta = client.get("/api/language/meta")
    assert meta.status_code == 200
    assert meta.json()["language_ready"] is True

    interpret = client.post(
        "/api/language/query/interpret",
        json={"query": "top 5 hospitalization risk with diabetes"},
    )
    assert interpret.status_code == 200
    payload = interpret.json()
    query_id = payload["query_id"]
    assert payload["action"] == "list_beneficiaries"

    blocked = client.post(
        "/api/language/query/execute",
        json={"query_id": query_id, "confirmed": False},
    )
    assert blocked.status_code == 400

    executed = client.post(
        "/api/language/query/execute",
        json={"query_id": query_id, "confirmed": True},
    )
    assert executed.status_code == 200
    result = executed.json()
    assert result["row_count"] >= 1
    assert result["claims"]
    assert load_result(query_id, settings=language_settings) is not None

    summary = client.get("/api/beneficiaries/B1")
    assert summary.status_code == 200

    grounded = client.get("/api/language/summary/B1", params={"analytic_year": 2019})
    assert grounded.status_code == 200
    assert grounded.json()["narrative"]
    assert grounded.json()["grounded"]["claims"]


def test_meta_reports_phase_seven(language_settings: Settings, monkeypatch) -> None:
    _patch_settings(monkeypatch, language_settings)
    client = TestClient(app)
    response = client.get("/api/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["prototype_phase"] == "8"
    assert payload["language_ready"] is False
