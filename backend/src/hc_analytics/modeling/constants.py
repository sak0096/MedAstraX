from __future__ import annotations

from enum import Enum

MODEL_SCHEMA_VERSION = "1.0"

# Primary XGBoost scores are exposed as dashboard risk columns.
PRIMARY_MODEL_FAMILY = "xgboost"

FEATURE_COLUMNS = [
    "age",
    "sex",
    "race",
    "state_code",
    "esrd_ind",
    "inpatient_claims",
    "outpatient_claims",
    "carrier_claims",
    "snf_claims",
    "dme_claims",
    "hha_claims",
    "hospice_claims",
    "total_claims",
    "total_payment_amt",
    "inpatient_payment_amt",
    "rx_fill_count",
    "rx_unique_drugs",
    "rx_days_supply",
    "distinct_diagnosis_count",
    "has_diabetes",
    "has_chf",
    "has_copd",
    "has_ckd",
    "has_hypertension",
    "chronic_condition_count",
    "readmission_30d_count",
]

CATEGORICAL_COLUMNS = ["sex", "race", "state_code", "esrd_ind"]

MODEL_FAMILIES = ("logistic_regression", "xgboost")


class RiskTarget(str, Enum):
    HOSPITALIZATION = "next_year_hospitalization"
    HIGH_UTILIZATION = "next_year_high_utilization"
    ELEVATED_COST = "next_year_elevated_cost"


TARGET_SHORT_NAMES = {
    RiskTarget.HOSPITALIZATION: "hospitalization",
    RiskTarget.HIGH_UTILIZATION: "high_utilization",
    RiskTarget.ELEVATED_COST: "elevated_cost",
}


def risk_score_column(target: RiskTarget, family: str = PRIMARY_MODEL_FAMILY) -> str:
    short = TARGET_SHORT_NAMES[target]
    if family == PRIMARY_MODEL_FAMILY:
        return f"{short}_risk"
    return f"{short}_risk_{family}"
