"""Feature engineering pipeline (Phase 2)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from hc_analytics.config import Settings, get_settings
from hc_analytics.features.aggregators import (
    add_next_year_labels,
    aggregate_claim_features,
    aggregate_prescription_features,
    attach_demographics,
)
from hc_analytics.features.cohort_summary import write_cohort_summary
from hc_analytics.features.constants import FEATURE_OUTPUT_COLUMNS, FEATURE_SCHEMA_VERSION
from hc_analytics.ingestion.io import git_commit_hash


def _load_processed_table(processed_dir: Path, name: str) -> pd.DataFrame:
    path = processed_dir / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing processed table: {path}")
    return pd.read_parquet(path)


def build_feature_store(
    beneficiaries: pd.DataFrame,
    claims: pd.DataFrame,
    prescriptions: pd.DataFrame,
) -> pd.DataFrame:
    base = beneficiaries.rename(columns={"reference_year": "analytic_year"})[
        ["bene_id", "analytic_year"]
    ].drop_duplicates()

    claim_features = aggregate_claim_features(claims)
    rx_features = aggregate_prescription_features(prescriptions)

    features = base.merge(claim_features, on=["bene_id", "analytic_year"], how="left")
    features = features.merge(rx_features, on=["bene_id", "analytic_year"], how="left")
    features = attach_demographics(features, beneficiaries)

    numeric_defaults = {
        "inpatient_claims": 0,
        "outpatient_claims": 0,
        "carrier_claims": 0,
        "snf_claims": 0,
        "dme_claims": 0,
        "hha_claims": 0,
        "hospice_claims": 0,
        "total_claims": 0,
        "total_payment_amt": 0.0,
        "inpatient_payment_amt": 0.0,
        "rx_fill_count": 0,
        "rx_unique_drugs": 0,
        "rx_days_supply": 0,
        "distinct_diagnosis_count": 0,
        "has_diabetes": 0,
        "has_chf": 0,
        "has_copd": 0,
        "has_ckd": 0,
        "has_hypertension": 0,
        "chronic_condition_count": 0,
        "readmission_30d_count": 0,
    }
    for column, default in numeric_defaults.items():
        if column not in features.columns:
            features[column] = default
        features[column] = features[column].fillna(default)

    features = add_next_year_labels(features)
    for column in FEATURE_OUTPUT_COLUMNS:
        if column not in features.columns:
            features[column] = pd.NA
    return features[FEATURE_OUTPUT_COLUMNS].sort_values(["bene_id", "analytic_year"]).reset_index(drop=True)


def _write_feature_manifest(
    *,
    settings: Settings,
    row_count: int,
) -> Path:
    manifest_path = settings.artifacts_path / "feature_manifest.json"
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit_hash(settings.repo_root),
        "row_count": row_count,
        "output": str(settings.processed_data_path / "feature_store.parquet"),
        "cohort_summary": str(settings.artifacts_path / "cohort_summary.json"),
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def run_feature_engineering(settings: Optional[Settings] = None) -> Dict[str, object]:
    settings = settings or get_settings()
    processed_dir = settings.processed_data_path
    processed_dir.mkdir(parents=True, exist_ok=True)

    beneficiaries = _load_processed_table(processed_dir, "beneficiaries")
    claims = _load_processed_table(processed_dir, "claims")
    prescriptions = _load_processed_table(processed_dir, "prescription_events")

    if claims["service_from_dt"].isna().all():
        raise ValueError(
            "Claims dates are missing. Re-run ingestion after updating date parsing."
        )

    features = build_feature_store(beneficiaries, claims, prescriptions)
    feature_path = processed_dir / "feature_store.parquet"
    features.to_parquet(feature_path, index=False)
    cohort_path = write_cohort_summary(features, settings.artifacts_path / "cohort_summary.json")
    _write_feature_manifest(settings=settings, row_count=len(features))

    return {
        "feature_rows": len(features),
        "feature_store": str(feature_path),
        "cohort_summary": str(cohort_path),
    }
