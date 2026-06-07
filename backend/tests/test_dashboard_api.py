from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.features.cohort_summary import write_cohort_summary
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
def dashboard_settings(tmp_path: Path) -> Settings:
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
    features.to_parquet(processed / "feature_store.parquet", index=False)
    write_cohort_summary(features, artifacts / "cohort_summary.json")
    return Settings(
        repo_root=tmp_path,
        data_processed_dir=Path("data/processed"),
        artifacts_dir=Path("artifacts"),
    )


def _patch_settings(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr("hc_analytics.api.app.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.api.data_access.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.api.routes.predictions.get_settings", lambda: settings)


def test_cohort_summary_api_returns_chart_sections(
    dashboard_settings: Settings,
    monkeypatch,
) -> None:
    run_training(dashboard_settings, test_year_count=2)
    _patch_settings(monkeypatch, dashboard_settings)

    client = TestClient(app)
    response = client.get("/api/cohort/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["beneficiary_years"] == 20
    assert "by_chronic_condition" in payload
    assert len(payload["by_chronic_condition"]) == 5
    assert "utilization_distribution" in payload
    assert "cost_distribution" in payload


def test_beneficiary_list_and_detail_api(
    dashboard_settings: Settings,
    monkeypatch,
) -> None:
    run_training(dashboard_settings, test_year_count=2)
    _patch_settings(monkeypatch, dashboard_settings)

    client = TestClient(app)
    listing = client.get(
        "/api/beneficiaries",
        params={"limit": 5, "sort_by": "hospitalization_risk"},
    )
    assert listing.status_code == 200
    rows = listing.json()["rows"]
    assert len(rows) == 5
    assert "age" in rows[0]
    assert "hospitalization_risk" in rows[0]

    detail = client.get("/api/beneficiaries/B1")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["bene_id"] == "B1"
    assert "risk_scores" in payload
    assert "utilization" in payload
    assert "diagnosis" in payload
    assert len(payload["history"]) >= 1


def test_meta_reports_phase_seven(dashboard_settings: Settings, monkeypatch) -> None:
    _patch_settings(monkeypatch, dashboard_settings)
    client = TestClient(app)
    response = client.get("/api/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["prototype_phase"] == "7"
    assert "language_ready" in payload
