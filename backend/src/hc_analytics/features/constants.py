from __future__ import annotations

FEATURE_SCHEMA_VERSION = "1.0"

# ICD-10-CM prefix groups used as chronic-condition proxies for dashboard features.
CHRONIC_CONDITION_PREFIXES = {
    "has_diabetes": ("E10", "E11", "E13"),
    "has_chf": ("I50",),
    "has_copd": ("J44",),
    "has_ckd": ("N18",),
    "has_hypertension": ("I10", "I11", "I12", "I13", "I15", "I16"),
}

FEATURE_OUTPUT_COLUMNS = [
    "bene_id",
    "analytic_year",
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
    "next_year_hospitalization",
    "next_year_high_utilization",
    "next_year_elevated_cost",
]
