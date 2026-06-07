from __future__ import annotations

from typing import Dict, Iterable

import numpy as np
import pandas as pd

from hc_analytics.features.constants import CHRONIC_CONDITION_PREFIXES


def _normalize_diagnosis(code: object) -> str:
    if pd.isna(code):
        return ""
    return str(code).strip().upper().replace(".", "")


def chronic_flags_from_codes(codes: Iterable[object]) -> Dict[str, int]:
    normalized = {_normalize_diagnosis(code) for code in codes if _normalize_diagnosis(code)}
    flags: Dict[str, int] = {}
    for feature_name, prefixes in CHRONIC_CONDITION_PREFIXES.items():
        flags[feature_name] = int(
            any(code.startswith(prefix) for code in normalized for prefix in prefixes)
        )
    flags["chronic_condition_count"] = sum(
        flags[name] for name in CHRONIC_CONDITION_PREFIXES if flags[name]
    )
    return flags


def aggregate_claim_features(claims: pd.DataFrame) -> pd.DataFrame:
    claims = claims.copy()
    claims["service_year"] = claims["service_from_dt"].dt.year
    claims = claims[claims["service_year"].notna()].copy()
    claims["payment_amt"] = claims["payment_amt"].fillna(0.0)

    counts = (
        claims.groupby(["bene_id", "service_year", "claim_setting"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    counts = counts.rename(columns={"service_year": "analytic_year"})

    payments = (
        claims.groupby(["bene_id", "service_year"])
        .agg(
            total_payment_amt=("payment_amt", "sum"),
            distinct_diagnosis_count=("principal_diagnosis_cd", "nunique"),
        )
        .reset_index()
        .rename(columns={"service_year": "analytic_year"})
    )

    inpatient_payments = (
        claims.loc[claims["claim_setting"] == "inpatient"]
        .groupby(["bene_id", "service_year"])["payment_amt"]
        .sum()
        .reset_index()
        .rename(
            columns={
                "service_year": "analytic_year",
                "payment_amt": "inpatient_payment_amt",
            }
        )
    )

    chronic_rows = []
    for (bene_id, service_year), group in claims.groupby(["bene_id", "service_year"]):
        flags = chronic_flags_from_codes(group["principal_diagnosis_cd"].tolist())
        chronic_rows.append({"bene_id": bene_id, "analytic_year": int(service_year), **flags})
    chronic = pd.DataFrame(chronic_rows)

    readmissions = compute_readmission_counts(
        claims.loc[claims["claim_setting"] == "inpatient", ["bene_id", "service_from_dt", "service_thru_dt"]]
    )

    feature_frames = [counts, payments, inpatient_payments, chronic, readmissions]
    merged = feature_frames[0]
    for frame in feature_frames[1:]:
        merged = merged.merge(frame, on=["bene_id", "analytic_year"], how="outer")

    setting_columns = [
        "inpatient",
        "outpatient",
        "carrier",
        "snf",
        "dme",
        "hha",
        "hospice",
    ]
    rename_map = {setting: f"{setting}_claims" for setting in setting_columns}
    merged = merged.rename(columns=rename_map)
    for column in rename_map.values():
        if column not in merged.columns:
            merged[column] = 0
        merged[column] = merged[column].fillna(0).astype(int)

    claim_count_columns = list(rename_map.values())
    merged["total_claims"] = merged[claim_count_columns].sum(axis=1)
    merged["inpatient_payment_amt"] = merged["inpatient_payment_amt"].fillna(0.0)
    for column in CHRONIC_CONDITION_PREFIXES:
        if column not in merged.columns:
            merged[column] = 0
        merged[column] = merged[column].fillna(0).astype(int)
    if "chronic_condition_count" not in merged.columns:
        merged["chronic_condition_count"] = 0
    merged["chronic_condition_count"] = merged["chronic_condition_count"].fillna(0).astype(int)
    merged["readmission_30d_count"] = merged["readmission_30d_count"].fillna(0).astype(int)
    return merged


def compute_readmission_counts(inpatient_claims: pd.DataFrame) -> pd.DataFrame:
    if inpatient_claims.empty:
        return pd.DataFrame(columns=["bene_id", "analytic_year", "readmission_30d_count"])

    stays = inpatient_claims.dropna(subset=["service_thru_dt"]).copy()
    stays["service_year"] = stays["service_thru_dt"].dt.year
    stays = stays.sort_values(["bene_id", "service_thru_dt"])

    readmission_rows = []
    for bene_id, group in stays.groupby("bene_id"):
        discharge_dates = group["service_thru_dt"].tolist()
        years = group["service_year"].tolist()
        for index in range(1, len(discharge_dates)):
            gap_days = (discharge_dates[index] - discharge_dates[index - 1]).days
            if 0 < gap_days <= 30:
                readmission_rows.append(
                    {"bene_id": bene_id, "analytic_year": int(years[index]), "readmission_30d_count": 1}
                )

    if not readmission_rows:
        return pd.DataFrame(columns=["bene_id", "analytic_year", "readmission_30d_count"])

    return (
        pd.DataFrame(readmission_rows)
        .groupby(["bene_id", "analytic_year"], as_index=False)["readmission_30d_count"]
        .sum()
    )


def aggregate_prescription_features(prescriptions: pd.DataFrame) -> pd.DataFrame:
    prescriptions = prescriptions.copy()
    prescriptions["service_year"] = prescriptions["service_dt"].dt.year
    prescriptions = prescriptions[prescriptions["service_year"].notna()].copy()
    aggregated = (
        prescriptions.groupby(["bene_id", "service_year"])
        .agg(
            rx_fill_count=("pde_id", "count"),
            rx_unique_drugs=("product_service_id", "nunique"),
            rx_days_supply=("days_supply", "sum"),
        )
        .reset_index()
        .rename(columns={"service_year": "analytic_year"})
    )
    aggregated["rx_days_supply"] = aggregated["rx_days_supply"].fillna(0).astype(int)
    return aggregated


def attach_demographics(features: pd.DataFrame, beneficiaries: pd.DataFrame) -> pd.DataFrame:
    demo = beneficiaries.rename(
        columns={
            "reference_year": "analytic_year",
            "age_at_end_ref_yr": "age",
            "sex_ident_cd": "sex",
            "bene_race_cd": "race",
            "esrd_ind": "esrd_ind",
        }
    )
    demo = demo[
        [
            "bene_id",
            "analytic_year",
            "age",
            "sex",
            "race",
            "state_code",
            "esrd_ind",
        ]
    ]
    return features.merge(demo, on=["bene_id", "analytic_year"], how="left")


def add_next_year_labels(features: pd.DataFrame) -> pd.DataFrame:
    labeled = features.sort_values(["bene_id", "analytic_year"]).copy()
    grouped = labeled.groupby("bene_id", sort=False)

    next_inpatient = grouped["inpatient_claims"].shift(-1).fillna(0)
    next_claims = grouped["total_claims"].shift(-1).fillna(0)
    next_cost = grouped["total_payment_amt"].shift(-1).fillna(0.0)

    claims_threshold = next_claims[next_claims > 0].quantile(0.75)
    cost_threshold = next_cost[next_cost > 0].quantile(0.75)

    labeled["next_year_hospitalization"] = next_inpatient.gt(0).astype(int)
    labeled["next_year_high_utilization"] = (next_claims >= claims_threshold).fillna(False).astype(int)
    labeled["next_year_elevated_cost"] = (next_cost >= cost_threshold).fillna(False).astype(int)
    return labeled
