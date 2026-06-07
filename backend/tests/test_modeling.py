from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.modeling.constants import (
    FEATURE_COLUMNS,
    RiskTarget,
    risk_score_column,
)
from hc_analytics.modeling.pipeline import (
    _frame_with_modeling_labels,
    _rows_with_valid_next_year,
    build_predictions,
    run_training,
)
from hc_analytics.modeling.split import time_based_year_split


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
def modeling_settings(tmp_path: Path) -> Settings:
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

    return Settings(
        repo_root=tmp_path,
        data_raw_dir=Path("data/raw"),
        data_processed_dir=Path("data/processed"),
        artifacts_dir=Path("artifacts"),
    )


def test_frame_with_modeling_labels_uses_calendar_next_year() -> None:
    frame = pd.DataFrame(
        {
            "bene_id": ["B1", "B1", "B1"],
            "analytic_year": [2021, 2022, 2023],
            "inpatient_claims": [0, 2, 1],
            "total_claims": [4, 8, 6],
            "total_payment_amt": [100.0, 500.0, 300.0],
            "next_year_hospitalization": [0, 0, 0],
            "next_year_high_utilization": [0, 0, 0],
            "next_year_elevated_cost": [0, 0, 0],
        }
    )
    labeled = _frame_with_modeling_labels(frame)
    row_2021 = labeled.loc[labeled["analytic_year"] == 2021].iloc[0]

    assert row_2021[RiskTarget.HOSPITALIZATION.value] == 1
    assert len(labeled) == 2


def test_rows_with_valid_next_year_requires_consecutive_followup() -> None:
    frame = pd.DataFrame(
        {
            "bene_id": ["B1", "B1", "B2", "B2"],
            "analytic_year": [2020, 2022, 2021, 2022],
            "next_year_hospitalization": [0, 1, 1, 0],
        }
    )
    valid = _rows_with_valid_next_year(frame)

    assert len(valid) == 1
    assert valid.iloc[0]["bene_id"] == "B2"
    assert valid.iloc[0]["analytic_year"] == 2021


def test_time_based_year_split_holds_out_recent_years() -> None:
    frame = pd.DataFrame(
        {
            "bene_id": ["B1"] * 5,
            "analytic_year": [2019, 2020, 2021, 2022, 2023],
            "next_year_hospitalization": [0, 1, 0, 1, 0],
        }
    )
    train, test, spec = time_based_year_split(
        frame,
        label_column="next_year_hospitalization",
        test_year_count=2,
    )

    assert spec.test_years == (2020, 2022)
    assert spec.train_years == (2019, 2021, 2023)
    assert len(train) == 3
    assert len(test) == 2


def test_run_training_writes_models_predictions_and_manifest(
    modeling_settings: Settings,
) -> None:
    result = run_training(modeling_settings, test_year_count=2)

    predictions_path = Path(result["predictions"])
    manifest_path = Path(result["manifest"])
    models_dir = Path(result["models_dir"])

    assert predictions_path.exists()
    assert manifest_path.exists()
    assert result["prediction_rows"] == 20
    assert len(list(models_dir.rglob("*.joblib"))) in {3, 6}

    predictions = pd.read_parquet(predictions_path)
    for target in RiskTarget:
        assert risk_score_column(target) in predictions.columns
        assert risk_score_column(target, "logistic_regression") in predictions.columns or (
            risk_score_column(target) == risk_score_column(target, "logistic_regression")
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert len(manifest["targets"]) == 3


def test_build_predictions_scores_all_feature_rows(modeling_settings: Settings) -> None:
    run_training(modeling_settings, test_year_count=2)
    predictions = build_predictions(modeling_settings)

    assert len(predictions) == 20
    assert predictions["hospitalization_risk"].between(0, 1).all()
    assert set(predictions.columns).issuperset({"model_version", "primary_model_family"})


def test_prediction_api_returns_rows(modeling_settings: Settings, monkeypatch) -> None:
    run_training(modeling_settings, test_year_count=2)
    monkeypatch.setattr(
        "hc_analytics.api.routes.predictions.get_settings",
        lambda: modeling_settings,
    )
    monkeypatch.setattr(
        "hc_analytics.api.app.get_settings",
        lambda: modeling_settings,
    )

    client = TestClient(app)
    response = client.get("/api/predictions", params={"limit": 5, "sort_by": "hospitalization_risk"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 5
    assert "hospitalization_risk" in payload["rows"][0]

    detail = client.get("/api/predictions/B1")
    assert detail.status_code == 200
    assert detail.json()["bene_id"] == "B1"

    meta = client.get("/api/models/meta")
    assert meta.status_code == 200
    assert meta.json()["predictions_ready"] is True
