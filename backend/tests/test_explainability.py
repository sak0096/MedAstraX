from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.explainability.bundles import EvidenceBundle
from hc_analytics.explainability.pipeline import (
    load_cached_bundle,
    load_global_importance,
    run_explainability,
)
from hc_analytics.explainability.shap_engine import aggregate_shap_to_features, top_contributors
from hc_analytics.explainability.stability import bootstrap_top_feature_stability, stability_from_margin
from hc_analytics.modeling.constants import RiskTarget
from hc_analytics.modeling.pipeline import run_training
from hc_analytics.modeling.trainers import build_model_pipeline


@pytest.fixture()
def explainability_settings(tmp_path: Path) -> Settings:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)

    rows = []
    for year in (2019, 2020, 2021, 2022, 2023):
        for index, bene_id in enumerate(("B1", "B2", "B3", "B4")):
            rows.append(
                {
                    "bene_id": bene_id,
                    "analytic_year": year,
                    "age": 70 + index,
                    "sex": "1",
                    "race": "1",
                    "state_code": "01",
                    "esrd_ind": "0",
                    "inpatient_claims": 1 if (index + year) % 2 == 0 else 0,
                    "outpatient_claims": 2,
                    "carrier_claims": 3,
                    "snf_claims": 0,
                    "dme_claims": 0,
                    "hha_claims": 0,
                    "hospice_claims": 0,
                    "total_claims": 5 + index,
                    "total_payment_amt": 1000.0 + (index * 250) + year,
                    "inpatient_payment_amt": 500.0,
                    "rx_fill_count": 4,
                    "rx_unique_drugs": 2,
                    "rx_days_supply": 90,
                    "distinct_diagnosis_count": 2,
                    "has_diabetes": 0,
                    "has_chf": int(index % 2 == 0),
                    "has_copd": 0,
                    "has_ckd": 0,
                    "has_hypertension": 1,
                    "chronic_condition_count": 1,
                    "readmission_30d_count": 0,
                    "next_year_hospitalization": int((index + year) % 3 == 0),
                    "next_year_high_utilization": int(index >= 2),
                    "next_year_elevated_cost": int(index % 2 == 1),
                }
            )

    features = pd.DataFrame(rows)
    features.to_parquet(processed / "feature_store.parquet", index=False)

    return Settings(
        repo_root=tmp_path,
        data_raw_dir=Path("data/raw"),
        data_processed_dir=Path("data/processed"),
        artifacts_dir=Path("artifacts"),
    )


def test_aggregate_shap_maps_one_hot_columns_back_to_parent_features() -> None:
    names = ["numeric__age", "categorical__sex_1", "categorical__sex_2"]
    shap_row = [0.5, 0.2, -0.1]
    aggregated = aggregate_shap_to_features(names, shap_row)

    assert aggregated["age"] == 0.5
    assert aggregated["sex"] == pytest.approx(0.1)


def test_top_contributors_returns_ranked_directional_rows() -> None:
    rows = top_contributors(
        {"age": 0.4, "total_claims": -0.2, "has_chf": 0.1},
        top_k=2,
        feature_values={"age": 72},
    )

    assert rows[0]["feature"] == "age"
    assert rows[0]["direction"] == "increases_risk"
    assert rows[1]["direction"] == "decreases_risk"
    assert rows[0]["feature_value"] == 72


def test_stability_from_margin_assigns_badges() -> None:
    assert stability_from_margin([0.5, 0.1])[0] == "green"
    assert stability_from_margin([0.2, 0.15])[0] == "yellow"
    assert stability_from_margin([0.1, 0.09])[0] == "red"


def test_bootstrap_top_feature_stability_returns_badge() -> None:
    frame = pd.DataFrame(
        {
            "age": [70, 71, 72, 73],
            "sex": ["1", "1", "2", "2"],
            "race": ["1", "1", "1", "1"],
            "state_code": ["01", "01", "01", "01"],
            "esrd_ind": ["0", "0", "0", "0"],
            "inpatient_claims": [0, 1, 2, 3],
            "outpatient_claims": [1, 1, 2, 2],
            "carrier_claims": [1, 2, 2, 3],
            "snf_claims": [0, 0, 0, 0],
            "dme_claims": [0, 0, 0, 0],
            "hha_claims": [0, 0, 0, 0],
            "hospice_claims": [0, 0, 0, 0],
            "total_claims": [2, 4, 6, 8],
            "total_payment_amt": [100.0, 200.0, 300.0, 400.0],
            "inpatient_payment_amt": [0.0, 100.0, 200.0, 300.0],
            "rx_fill_count": [1, 2, 2, 3],
            "rx_unique_drugs": [1, 1, 2, 2],
            "rx_days_supply": [30, 30, 60, 60],
            "distinct_diagnosis_count": [1, 1, 2, 2],
            "has_diabetes": [0, 0, 1, 1],
            "has_chf": [0, 1, 1, 1],
            "has_copd": [0, 0, 0, 1],
            "has_ckd": [0, 0, 0, 0],
            "has_hypertension": [1, 1, 1, 1],
            "chronic_condition_count": [1, 2, 3, 4],
            "readmission_30d_count": [0, 0, 1, 0],
        }
    )
    labels = pd.Series([0, 0, 1, 1])
    pipeline = build_model_pipeline("logistic_regression")
    pipeline.fit(frame, labels)

    badge, score, top_feature = bootstrap_top_feature_stability(
        pipeline,
        frame.iloc[2],
        background=frame,
        bootstrap_iterations=3,
        random_state=7,
    )
    assert badge in {"green", "yellow", "red"}
    assert 0.0 <= score <= 1.0
    assert top_feature


def test_run_explainability_writes_global_local_and_bundle_artifacts(
    explainability_settings: Settings,
) -> None:
    run_training(explainability_settings, test_year_count=2)
    result = run_explainability(explainability_settings, top_k=3, max_rows=8)

    explanations_dir = Path(result["explanations_dir"])
    assert Path(result["manifest"]).exists()
    assert Path(result["local_topk"]).exists()
    assert result["bundle_count"] == 8
    assert json.loads((explanations_dir / "manifest.json").read_text())["top_k"] == 3

    global_payload = load_global_importance(RiskTarget.HOSPITALIZATION, explainability_settings)
    assert global_payload is not None
    assert len(global_payload["importance"]) > 0

    bundle = load_cached_bundle("B1", 2019, explainability_settings)
    assert bundle is not None
    assert bundle.schema_version == "1.0"
    assert len(bundle.targets) == 3
    assert bundle.grounded.claims


def test_explanation_api_returns_global_local_and_bundle(
    explainability_settings: Settings,
    monkeypatch,
) -> None:
    run_training(explainability_settings, test_year_count=2)
    run_explainability(explainability_settings, top_k=3, max_rows=8)
    monkeypatch.setattr(
        "hc_analytics.api.routes.explanations.get_settings",
        lambda: explainability_settings,
    )
    monkeypatch.setattr(
        "hc_analytics.api.app.get_settings",
        lambda: explainability_settings,
    )

    client = TestClient(app)
    meta = client.get("/api/explanations/meta")
    assert meta.status_code == 200
    assert meta.json()["explanations_ready"] is True

    global_response = client.get("/api/explanations/global", params={"target": "hospitalization"})
    assert global_response.status_code == 200
    assert "importance" in global_response.json()

    local_response = client.get("/api/explanations/B1", params={"analytic_year": 2019, "top_k": 3})
    assert local_response.status_code == 200
    assert local_response.json()["contributors"]

    bundle_response = client.get("/api/explanations/B1/bundle", params={"analytic_year": 2019})
    assert bundle_response.status_code == 200
    EvidenceBundle.model_validate(bundle_response.json())
