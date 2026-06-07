from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pandas as pd


def build_cohort_summary(features: pd.DataFrame) -> Dict[str, object]:
    working = features.copy()
    working["age_group"] = pd.cut(
        working["age"],
        bins=[0, 64, 74, 84, 200],
        labels=["<65", "65-74", "75-84", "85+"],
        right=True,
    )

    summary: Dict[str, object] = {
        "beneficiary_years": int(len(working)),
        "distinct_beneficiaries": int(working["bene_id"].nunique()),
        "analytic_years": sorted(int(year) for year in working["analytic_year"].dropna().unique()),
        "avg_total_claims": float(working["total_claims"].mean()),
        "avg_total_payment_amt": float(working["total_payment_amt"].mean()),
        "hospitalization_rate_next_year": float(working["next_year_hospitalization"].mean()),
        "by_state": (
            working.groupby("state_code", dropna=False)
            .agg(
                beneficiary_years=("bene_id", "count"),
                avg_total_claims=("total_claims", "mean"),
                avg_payment_amt=("total_payment_amt", "mean"),
            )
            .reset_index()
            .to_dict(orient="records")
        ),
        "by_age_group": (
            working.loc[working["age_group"].notna()]
            .groupby("age_group", observed=True)
            .agg(
                beneficiary_years=("bene_id", "count"),
                avg_total_claims=("total_claims", "mean"),
                hospitalization_rate_next_year=("next_year_hospitalization", "mean"),
            )
            .reset_index()
            .to_dict(orient="records")
        ),
    }
    return summary


def write_cohort_summary(features: pd.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_cohort_summary(features)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path
