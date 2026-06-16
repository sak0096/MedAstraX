#!/usr/bin/env python3
"""Regenerate study/study_cases.json from local feature store and SHAP artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = {
    "B-01": "-10000010263023",
    "B-02": "-10000010266687",
    "B-03": "-10000010279991",
    "B-04": "-10000010259786",
    "B-07": "-10000010260449",
    "B-09": "-10000010271299",
    "B-12": "-10000010273042",
    "B-15": "-10000010266211",
}


def top_features(topk: pd.DataFrame, bene_id: str, year: int, n: int = 3) -> list[dict]:
    frame = topk[
        (topk["bene_id"] == bene_id)
        & (topk["analytic_year"] == year)
        & (topk["target"] == "next_year_hospitalization")
    ].sort_values("rank")
    return [
        {
            "feature": row["feature"],
            "shap_value": float(row["shap_value"]),
            "direction": row["direction"],
            "rank": int(row["rank"]),
        }
        for _, row in frame.head(n).iterrows()
    ]


def main() -> None:
    fs = pd.read_parquet(REPO_ROOT / "data/processed/feature_store.parquet")
    pred = pd.read_parquet(REPO_ROOT / "data/processed/predictions.parquet")
    topk = pd.read_parquet(REPO_ROOT / "artifacts/explanations/local_topk.parquet")
    merged = fs.merge(
        pred[
            [
                "bene_id",
                "analytic_year",
                "hospitalization_risk",
                "high_utilization_risk",
                "elevated_cost_risk",
            ]
        ],
        on=["bene_id", "analytic_year"],
    )
    year = 2022
    subset = merged[merged["analytic_year"] == year]

    cases = []
    for case_id, bene_id in CASE_IDS.items():
        row = subset[subset["bene_id"] == bene_id].iloc[0]
        m3 = (
            {
                "type": "false_narrative_claim",
                "statement": "Beneficiary has active diabetes management needs driving utilization.",
                "source_fields": ["has_diabetes"],
                "contradicts_field": "has_diabetes",
                "contradicts_expected": 0,
            }
            if int(row["has_diabetes"]) == 0
            else {
                "type": "false_narrative_claim",
                "statement": "Heart failure is the dominant chronic driver for this beneficiary.",
                "source_fields": ["has_chf"],
                "contradicts_field": "has_chf",
                "contradicts_expected": 0,
            }
        )
        cases.append(
            {
                "case_id": case_id,
                "label": f"Case {case_id}",
                "bene_id": bene_id,
                "analytic_year": int(row["analytic_year"]),
                "ground_truth": {
                    "hospitalization_risk": round(float(row["hospitalization_risk"]), 6),
                    "high_utilization_risk": round(float(row["high_utilization_risk"]), 6),
                    "elevated_cost_risk": round(float(row["elevated_cost_risk"]), 6),
                    "chronic_condition_count": int(row["chronic_condition_count"]),
                    "has_diabetes": int(row["has_diabetes"]),
                    "has_chf": int(row["has_chf"]),
                    "top_hospitalization_features": top_features(topk, bene_id, year),
                },
                "manipulations": {
                    "M1": {"type": "inverted_shap", "target": "next_year_hospitalization"},
                    "M2": {"type": "misleading_risk", "risk_column": "hospitalization_risk", "delta": -0.25},
                    "M3": m3,
                    "M5": {
                        "type": "low_confidence",
                        "risk_columns": ["hospitalization_risk"],
                        "force_stability": "red",
                    },
                },
            }
        )

    existing_path = REPO_ROOT / "study" / "study_cases.json"
    tasks = []
    task_sets = {}
    manipulation_catalog = {}
    if existing_path.exists():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        tasks = existing.get("tasks", [])
        task_sets = existing.get("task_sets", {})
        manipulation_catalog = existing.get("manipulation_catalog", {})

    payload = {
        "schema_version": "1.0",
        "default_analytic_year": year,
        "manipulation_catalog": manipulation_catalog
        or {
            "M1": "Inverted local SHAP ranking (swap top 2 contributors)",
            "M2": "Misleading hospitalization risk display (±0.25)",
            "M3": "False grounded narrative claim contradicting record",
            "M4": "Incorrect NL query chronic filter",
            "M5": "Low-confidence risk framing + forced red stability",
        },
        "cases": cases,
        "tasks": tasks,
        "task_sets": task_sets,
    }
    output = REPO_ROOT / "study" / "study_cases.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
