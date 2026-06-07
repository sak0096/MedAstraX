from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from hc_analytics.config import Settings
from hc_analytics.features.pipeline import build_feature_store, run_feature_engineering


@pytest.fixture()
def feature_settings(tmp_path: Path) -> Settings:
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)

    beneficiaries = pd.DataFrame(
        {
            "bene_id": ["B1", "B1", "B2", "B2"],
            "reference_year": [2021, 2022, 2021, 2022],
            "age_at_end_ref_yr": [70, 71, 80, 81],
            "sex_ident_cd": ["1", "1", "2", "2"],
            "bene_race_cd": ["1", "1", "3", "3"],
            "state_code": ["01", "01", "13", "13"],
            "esrd_ind": ["0", "0", "0", "0"],
        }
    )
    claims = pd.DataFrame(
        {
            "bene_id": ["B1", "B1", "B1", "B2"],
            "claim_id": ["C1", "C2", "C3", "C4"],
            "claim_setting": ["inpatient", "carrier", "inpatient", "outpatient"],
            "service_from_dt": pd.to_datetime(
                ["2021-03-01", "2021-04-01", "2022-05-01", "2022-06-01"]
            ),
            "service_thru_dt": pd.to_datetime(
                ["2021-03-05", "2021-04-01", "2022-05-04", "2022-06-01"]
            ),
            "payment_amt": [1000.0, 200.0, 1500.0, 300.0],
            "provider_state_cd": ["01", "01", "01", "13"],
            "principal_diagnosis_cd": ["I509", "E119", "I509", "J440"],
            "clm_freq_cd": ["1", "1", "1", "1"],
            "hcpcs_cd": [pd.NA, "99213", pd.NA, pd.NA],
        }
    )
    prescriptions = pd.DataFrame(
        {
            "pde_id": ["P1", "P2"],
            "bene_id": ["B1", "B1"],
            "service_dt": pd.to_datetime(["2021-03-10", "2022-01-15"]),
            "paid_dt": pd.to_datetime(["2021-03-11", "2022-01-16"]),
            "product_service_id": ["DRUGA", "DRUGB"],
            "quantity_dispensed": [30, 30],
            "days_supply": [30, 30],
            "fill_number": [1, 1],
            "drug_coverage_status_cd": ["C", "C"],
        }
    )

    beneficiaries.to_parquet(processed / "beneficiaries.parquet", index=False)
    claims.to_parquet(processed / "claims.parquet", index=False)
    prescriptions.to_parquet(processed / "prescription_events.parquet", index=False)

    return Settings(
        repo_root=tmp_path,
        data_raw_dir=Path("data/raw"),
        data_processed_dir=Path("data/processed"),
        artifacts_dir=Path("artifacts"),
    )


def test_build_feature_store_computes_utilization_and_labels() -> None:
    beneficiaries = pd.DataFrame(
        {
            "bene_id": ["B1", "B1"],
            "reference_year": [2021, 2022],
            "age_at_end_ref_yr": [70, 71],
            "sex_ident_cd": ["1", "1"],
            "bene_race_cd": ["1", "1"],
            "state_code": ["01", "01"],
            "esrd_ind": ["0", "0"],
        }
    )
    claims = pd.DataFrame(
        {
            "bene_id": ["B1", "B1"],
            "claim_id": ["C1", "C2"],
            "claim_setting": ["inpatient", "inpatient"],
            "service_from_dt": pd.to_datetime(["2021-03-01", "2022-05-01"]),
            "service_thru_dt": pd.to_datetime(["2021-03-05", "2022-05-04"]),
            "payment_amt": [1000.0, 1500.0],
            "provider_state_cd": ["01", "01"],
            "principal_diagnosis_cd": ["I509", "I509"],
            "clm_freq_cd": ["1", "1"],
            "hcpcs_cd": [pd.NA, pd.NA],
        }
    )
    prescriptions = pd.DataFrame(
        {
            "pde_id": ["P1"],
            "bene_id": ["B1"],
            "service_dt": pd.to_datetime(["2021-03-10"]),
            "paid_dt": pd.to_datetime(["2021-03-11"]),
            "product_service_id": ["DRUGA"],
            "quantity_dispensed": [30],
            "days_supply": [30],
            "fill_number": [1],
            "drug_coverage_status_cd": ["C"],
        }
    )

    features = build_feature_store(beneficiaries, claims, prescriptions)
    row_2021 = features.loc[features["analytic_year"] == 2021].iloc[0]

    assert row_2021["inpatient_claims"] == 1
    assert row_2021["has_chf"] == 1
    assert row_2021["rx_fill_count"] == 1
    assert row_2021["next_year_hospitalization"] == 1


def test_run_feature_engineering_writes_outputs(feature_settings: Settings) -> None:
    result = run_feature_engineering(feature_settings)
    feature_path = Path(result["feature_store"])
    cohort_path = Path(result["cohort_summary"])

    assert feature_path.exists()
    assert cohort_path.exists()
    assert result["feature_rows"] == 4
    assert json.loads((feature_settings.artifacts_path / "feature_manifest.json").read_text())
