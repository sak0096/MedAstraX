from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import HTTPException

from hc_analytics.config import Settings, get_settings
from hc_analytics.features.constants import FEATURE_OUTPUT_COLUMNS
from hc_analytics.modeling.constants import RiskTarget, risk_score_column

PRIMARY_RISK_COLUMNS = [risk_score_column(target) for target in RiskTarget]

BENEFICIARY_LIST_COLUMNS = [
    "bene_id",
    "analytic_year",
    "age",
    "sex",
    "state_code",
    "total_claims",
    "total_payment_amt",
    "chronic_condition_count",
    "hospitalization_risk",
    "high_utilization_risk",
    "elevated_cost_risk",
]

CHRONIC_CONDITION_COLUMNS = [
    "has_diabetes",
    "has_chf",
    "has_copd",
    "has_ckd",
    "has_hypertension",
]

CHRONIC_CONDITION_LABELS = {
    "has_diabetes": "Diabetes",
    "has_chf": "Heart Failure",
    "has_copd": "COPD",
    "has_ckd": "Chronic Kidney Disease",
    "has_hypertension": "Hypertension",
}


def feature_store_path(settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    return settings.processed_data_path / "feature_store.parquet"


def predictions_path(settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    return settings.processed_data_path / "predictions.parquet"


def cohort_summary_path(settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    return settings.artifacts_path / "cohort_summary.json"


def load_feature_store(settings: Optional[Settings] = None) -> pd.DataFrame:
    settings = settings or get_settings()
    path = feature_store_path(settings)
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Feature store not available. Run `python -m hc_analytics.features` first.",
        )
    return pd.read_parquet(path)


def load_predictions(settings: Optional[Settings] = None) -> pd.DataFrame:
    settings = settings or get_settings()
    path = predictions_path(settings)
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Predictions not available. Run `python -m hc_analytics.modeling` first.",
        )
    return pd.read_parquet(path)


def load_merged_dashboard_frame(settings: Optional[Settings] = None) -> pd.DataFrame:
    features = load_feature_store(settings)
    predictions = load_predictions(settings)
    feature_columns = [column for column in FEATURE_OUTPUT_COLUMNS if column in features.columns]
    prediction_columns = [
        column
        for column in predictions.columns
        if column not in {"bene_id", "analytic_year"}
    ]
    merged = features[feature_columns].merge(
        predictions[["bene_id", "analytic_year", *prediction_columns]],
        on=["bene_id", "analytic_year"],
        how="inner",
    )
    if merged.empty:
        raise HTTPException(status_code=503, detail="No merged beneficiary records available.")
    return merged


def frame_to_records(frame: pd.DataFrame) -> List[Dict[str, object]]:
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def build_chart_enrichments(features: pd.DataFrame) -> Dict[str, object]:
    working = features.copy()
    by_chronic_condition = []
    for column, label in CHRONIC_CONDITION_LABELS.items():
        if column not in working.columns:
            continue
        prevalence = float(working[column].mean())
        by_chronic_condition.append(
            {
                "condition": label,
                "field": column,
                "prevalence": prevalence,
                "count": int(working[column].sum()),
            }
        )

    utilization_bins = [0, 5, 10, 20, 40, 1000]
    utilization_labels = ["0-5", "6-10", "11-20", "21-40", "41+"]
    working["utilization_bucket"] = pd.cut(
        working["total_claims"],
        bins=utilization_bins,
        labels=utilization_labels,
        right=True,
        include_lowest=True,
    )
    utilization_distribution = (
        working.groupby("utilization_bucket", observed=True)
        .size()
        .reset_index(name="beneficiary_years")
        .rename(columns={"utilization_bucket": "bucket"})
        .to_dict(orient="records")
    )

    cost_bins = [0, 10_000, 25_000, 50_000, 100_000, 1_000_000_000]
    cost_labels = ["<$10k", "$10k-$25k", "$25k-$50k", "$50k-$100k", "$100k+"]
    working["cost_bucket"] = pd.cut(
        working["total_payment_amt"],
        bins=cost_bins,
        labels=cost_labels,
        right=True,
        include_lowest=True,
    )
    cost_distribution = (
        working.groupby("cost_bucket", observed=True)
        .size()
        .reset_index(name="beneficiary_years")
        .rename(columns={"cost_bucket": "bucket"})
        .to_dict(orient="records")
    )

    return {
        "by_chronic_condition": by_chronic_condition,
        "utilization_distribution": utilization_distribution,
        "cost_distribution": cost_distribution,
    }


def load_cohort_summary_payload(settings: Optional[Settings] = None) -> Dict[str, object]:
    settings = settings or get_settings()
    summary_path = cohort_summary_path(settings)
    payload: Dict[str, object]
    if summary_path.exists():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    else:
        features = load_feature_store(settings)
        from hc_analytics.features.cohort_summary import build_cohort_summary

        payload = build_cohort_summary(features)

    features = load_feature_store(settings)
    payload.update(build_chart_enrichments(features))
    payload["risk_columns"] = list(PRIMARY_RISK_COLUMNS)
    return payload
