#!/usr/bin/env python3
"""Regenerate study/study_cases.json for dissertation study v2."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from hc_analytics.study.priority import PRIORITY_RULE_DESCRIPTION, PRIORITY_RULE_WEIGHTS, compute_priority_score

SHARED_CASE_IDS = {
    "B-07": "-10000010260449",
    "B-09": "-10000010271299",
    "B-12": "-10000010273042",
    "B-15": "-10000010266211",
}
# Fallback IDs used only when stratified sampling cannot find enough candidates.
FALLBACK_ALPHA_OUTREACH = {
    "B-01": "-10000010263023",
    "B-02": "-10000010266687",
    "B-03": "-10000010279991",
    "B-04": "-10000010259786",
}
FALLBACK_BETA_OUTREACH = {
    "B-01b": "-10000010275202",
    "B-02b": "-10000010262670",
    "B-03b": "-10000010256636",
    "B-04b": "-10000010265432",
}


def sample_matched_outreach_sets(
    subset: pd.DataFrame,
    *,
    seed: int = 42,
    quartet_size: int = 4,
) -> tuple[dict[str, str], dict[str, str], dict]:
    """Sample two matched outreach quartets from mid/high risk strata.

    Avoids the prior pattern of near-100th-percentile-only cases with unmatched
    alpha/beta priority difficulty.
    """
    frame = subset.copy()
    frame["priority_score"] = frame.apply(
        lambda row: compute_priority_score(
            {
                "inpatient_claims": row.get("inpatient_claims", 0),
                "outpatient_claims": row.get("outpatient_claims", 0),
                "chronic_condition_count": row.get("chronic_condition_count", 0),
                "total_claims": row.get("total_claims", 0),
            }
        ),
        axis=1,
    )
    # Keep clinically plausible high-risk but not exclusively extreme tails.
    risk_lo = float(frame["hospitalization_risk"].quantile(0.70))
    risk_hi = float(frame["hospitalization_risk"].quantile(0.97))
    reserved = set(SHARED_CASE_IDS.values())
    eligible = frame[
        (frame["hospitalization_risk"] >= risk_lo)
        & (frame["hospitalization_risk"] <= risk_hi)
        & (frame["total_claims"] >= 10)
        & (~frame["bene_id"].astype(str).isin(reserved))
    ].copy()
    if len(eligible) < quartet_size * 2:
        return FALLBACK_ALPHA_OUTREACH, FALLBACK_BETA_OUTREACH, {
            "method": "fallback_hardcoded",
            "reason": "insufficient_eligible_rows",
            "eligible_rows": int(len(eligible)),
        }

    eligible = eligible.sort_values("priority_score")
    eligible["priority_bin"] = pd.qcut(
        eligible["priority_score"],
        q=min(quartet_size, max(2, eligible["priority_score"].nunique())),
        labels=False,
        duplicates="drop",
    )
    rng = pd.Series(dtype=object)
    alpha: dict[str, str] = {}
    beta: dict[str, str] = {}
    used: set[str] = set()
    bins = sorted(eligible["priority_bin"].dropna().unique())
    generator = __import__("numpy").random.default_rng(seed)
    for index, bin_id in enumerate(bins[:quartet_size]):
        pool = eligible[eligible["priority_bin"] == bin_id]
        pool = pool[~pool["bene_id"].astype(str).isin(used)]
        if len(pool) < 2:
            continue
        chosen = pool.sample(n=2, random_state=int(generator.integers(0, 1_000_000)))
        alpha_id = f"B-0{index + 1}"
        beta_id = f"B-0{index + 1}b"
        alpha_bene = str(chosen.iloc[0]["bene_id"])
        beta_bene = str(chosen.iloc[1]["bene_id"])
        alpha[alpha_id] = alpha_bene
        beta[beta_id] = beta_bene
        used.update({alpha_bene, beta_bene})

    if len(alpha) < quartet_size or len(beta) < quartet_size:
        return FALLBACK_ALPHA_OUTREACH, FALLBACK_BETA_OUTREACH, {
            "method": "fallback_hardcoded",
            "reason": "insufficient_binned_pairs",
            "eligible_rows": int(len(eligible)),
        }

    meta = {
        "method": "stratified_priority_bins",
        "seed": seed,
        "risk_quantile_low": 0.70,
        "risk_quantile_high": 0.97,
        "risk_lo": risk_lo,
        "risk_hi": risk_hi,
        "eligible_rows": int(len(eligible)),
        "alpha_priority_scores": [
            float(eligible.loc[eligible["bene_id"].astype(str) == bene, "priority_score"].iloc[0])
            for bene in alpha.values()
        ],
        "beta_priority_scores": [
            float(eligible.loc[eligible["bene_id"].astype(str) == bene, "priority_score"].iloc[0])
            for bene in beta.values()
        ],
    }
    del rng
    return alpha, beta, meta


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


def false_narrative_config(row: pd.Series) -> dict:
    if int(row["has_diabetes"]) == 0:
        return {
            "type": "false_narrative_claim",
            "statement": "Beneficiary had two inpatient admissions in the analytic year.",
            "source_fields": ["inpatient_claims"],
            "contradicts_field": "inpatient_claims",
            "contradicts_expected": 0,
        }
    return {
        "type": "false_narrative_claim",
        "statement": "Heart failure is the dominant chronic driver for this beneficiary.",
        "source_fields": ["has_chf"],
        "contradicts_field": "has_chf",
        "contradicts_expected": 0,
    }


def build_case(
    case_id: str,
    bene_id: str,
    row: pd.Series,
    year: int,
    topk: pd.DataFrame,
    *,
    case_set: str,
) -> dict:
    ground_truth = {
        "hospitalization_risk": round(float(row["hospitalization_risk"]), 6),
        "high_utilization_risk": round(float(row["high_utilization_risk"]), 6),
        "elevated_cost_risk": round(float(row["elevated_cost_risk"]), 6),
        "chronic_condition_count": int(row["chronic_condition_count"]),
        "has_diabetes": int(row["has_diabetes"]),
        "has_chf": int(row["has_chf"]),
        "inpatient_claims": int(row["inpatient_claims"]),
        "outpatient_claims": int(row["outpatient_claims"]),
        "total_claims": int(row["total_claims"]),
        "top_hospitalization_features": top_features(topk, bene_id, year),
    }
    ground_truth["priority_score"] = compute_priority_score(ground_truth)
    return {
        "case_id": case_id,
        "label": f"Case {case_id}",
        "bene_id": bene_id,
        "analytic_year": int(row["analytic_year"]),
        "case_set": case_set,
        "ground_truth": ground_truth,
        "manipulations": {
            "M2": {"type": "incorrect_outreach_recommendation"},
            "M3": false_narrative_config(row),
            "M4": {
                "type": "incorrect_query_filter",
                "substitute_filter": "has_hypertension",
            },
            "M6": {
                "type": "incorrect_query_time_window",
                "displayed_months": 6,
                "actual_months": 12,
            },
            "M7": {"type": "omitted_query_threshold"},
        },
    }


def rank_outreach_cases(cases: list[dict]) -> list[str]:
    scored = sorted(
        cases,
        key=lambda case: case["ground_truth"]["priority_score"],
        reverse=True,
    )
    ranking = [case["case_id"] for case in scored]
    for case in cases:
        case["ground_truth"]["outreach_rank"] = ranking.index(case["case_id"]) + 1
        case["ground_truth"]["outreach_set_ranking"] = ranking
    return ranking


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
    alpha_map, beta_map, selection_meta = sample_matched_outreach_sets(subset, seed=42)

    cases: list[dict] = []
    alpha_outreach: list[dict] = []
    beta_outreach: list[dict] = []

    for case_id, bene_id in alpha_map.items():
        row = subset[subset["bene_id"] == bene_id].iloc[0]
        case = build_case(case_id, bene_id, row, year, topk, case_set="alpha")
        alpha_outreach.append(case)
        cases.append(case)

    for case_id, bene_id in beta_map.items():
        row = subset[subset["bene_id"] == bene_id].iloc[0]
        case = build_case(case_id, bene_id, row, year, topk, case_set="beta")
        beta_outreach.append(case)
        cases.append(case)

    rank_outreach_cases(alpha_outreach)
    rank_outreach_cases(beta_outreach)

    for case_id, bene_id in SHARED_CASE_IDS.items():
        row = subset[subset["bene_id"] == bene_id].iloc[0]
        cases.append(build_case(case_id, bene_id, row, year, topk, case_set="shared"))

    tasks = [
        {
            "task_id": "S1-T0",
            "study": "study1",
            "title": "Priority rule tutorial",
            "time_limit_min": 4,
            "instructions": "Review the operational priority rule panel, then complete the comprehension check before continuing.",
            "response_type": "comprehension",
            "requires_cases": [],
        },
        {
            "task_id": "S1-T1",
            "study": "study1",
            "title": "Cohort situational awareness",
            "time_limit_min": 4,
            "instructions": "Using the cohort overview only, answer: (a) Which age band has the highest next-year hospitalization rate? (b) Which chronic condition is most prevalent? (c) Approximate average total claims per beneficiary-year.",
            "response_type": "free_text",
            "requires_cases": [],
        },
        {
            "task_id": "S1-T2",
            "study": "study1",
            "title": "High-risk identification",
            "time_limit_min": 5,
            "instructions": "Sort the risk table by hospitalization risk (descending). Select the top 5 beneficiaries and record their IDs and risk percentages.",
            "response_type": "beneficiary_list",
            "requires_cases": [],
        },
        {
            "task_id": "S1-T3",
            "study": "study1",
            "title": "Risk driver interpretation",
            "time_limit_min": 6,
            "instructions": "Open Case B-07. What are the top 3 drivers of hospitalization risk? For each, state whether it increases or decreases risk.",
            "response_type": "feature_list",
            "requires_cases": ["B-07"],
        },
        {
            "task_id": "S1-T4a",
            "study": "study1",
            "title": "Global model literacy (tutorial)",
            "time_limit_min": 5,
            "instructions": "Tutorial only: switch the global importance view across risk targets. Which feature is most important for elevated cost risk at the cohort level?",
            "response_type": "free_text",
            "requires_cases": [],
            "conditions": ["xai"],
        },
        {
            "task_id": "S1-T4b",
            "study": "study1",
            "title": "Clinical judgment",
            "time_limit_min": 5,
            "instructions": "For Case B-12, using only profile panels, list three factors you would weigh for hospitalization risk and why.",
            "response_type": "free_text",
            "requires_cases": ["B-12"],
            "conditions": ["baseline"],
        },
        {
            "task_id": "S1-T5",
            "study": "study1",
            "title": "Outreach prioritization",
            "time_limit_min": 8,
            "instructions": "Rank your assigned outreach quartet using the operational priority rule taught in the tutorial. Submit an initial order, review the AI outreach recommendation (rule-based, not the risk model), then submit a final order with confidence. Feature contributions explain hospitalization risk scores, not the outreach ranking.",
            "response_type": "sequential_ranking",
            "requires_cases": [],
            "manipulation_slot": "study1",
            "sequential_judgment": True,
        },
        {
            "task_id": "S1-T6",
            "study": "study1",
            "title": "Explanation density (exploratory)",
            "time_limit_min": 4,
            "instructions": "For Case B-09, compare concise (top-3) vs expanded (top-5) explanations. Which helped more for an outreach decision?",
            "response_type": "preference",
            "requires_cases": ["B-09"],
            "conditions": ["xai"],
        },
        {
            "task_id": "S2-T0",
            "study": "study2",
            "title": "Dashboard tutorial",
            "time_limit_min": 3,
            "instructions": "Review how record summaries, source links, filters, and confirm-before-run search work, then complete the comprehension check.",
            "response_type": "comprehension",
            "requires_cases": [],
        },
        {
            "task_id": "S2-T1",
            "study": "study2",
            "title": "Manual cohort filtering",
            "time_limit_min": 5,
            "instructions": "Using the cohort filters and risk table for analytic year 2022, find beneficiaries with diabetes flagged, at least 50 claims, in the top 25 by hospitalization risk. Record the count and the highest-risk beneficiary ID.",
            "response_type": "cohort_selection",
            "requires_cases": [],
            "conditions": ["baseline"],
        },
        {
            "task_id": "S2-T2",
            "study": "study2",
            "title": "Natural-language cohort query",
            "time_limit_min": 5,
            "instructions": "Use the query box: 'Top 25 hospitalization risk with diabetes in the last 12 months with at least 50 claims.' Review the interpretation, confirm, and verify one result via drill-down.",
            "response_type": "query_flow",
            "requires_cases": [],
            "conditions": ["llm"],
            "manipulation_slot": "study2",
            "suggested_query": "Top 25 hospitalization risk with diabetes in the last 12 months with at least 50 claims",
        },
        {
            "task_id": "S2-T3",
            "study": "study2",
            "title": "Summary validation",
            "time_limit_min": 8,
            "instructions": "Open Case B-15. Using the record panels, decide whether a written summary of this case would be fully supported. After you submit that initial judgment, review the summary, flag any unsupported claim, and submit a final judgment with confidence.",
            "response_type": "sequential_claim_review",
            "requires_cases": ["B-15"],
            "conditions": ["llm"],
            "manipulation_slot": "study2",
            "sequential_judgment": True,
        },
        {
            "task_id": "S2-T4",
            "study": "study2",
            "title": "Cross-check summary vs record",
            "time_limit_min": 5,
            "instructions": "Using Case B-15, decide whether utilization is a key driver based on the summary and underlying panels.",
            "response_type": "free_text",
            "requires_cases": ["B-15"],
        },
        {
            "task_id": "S2-T5",
            "study": "study2",
            "title": "Cohort analytics query",
            "time_limit_min": 6,
            "instructions": "Ask: 'Cohort summary for chronic prevalence and hospitalization rate.' Answer which chronic condition is most prevalent.",
            "response_type": "free_text",
            "requires_cases": [],
            "conditions": ["llm"],
            "suggested_query": "Cohort summary for chronic prevalence and hospitalization rate",
        },
        {
            "task_id": "S2-T6",
            "study": "study2",
            "title": "Query control check",
            "time_limit_min": 5,
            "instructions": "Run: 'Top 10 elevated cost risk with heart failure in the last 12 months with at least 30 claims.' Cancel and rephrase if the interpretation looks wrong before confirming.",
            "response_type": "query_flow",
            "requires_cases": [],
            "conditions": ["llm"],
            "manipulation_slot": "study2",
            "suggested_query": "Top 10 elevated cost risk with heart failure in the last 12 months with at least 30 claims",
        },
        {
            "task_id": "S2-T7",
            "study": "study2",
            "title": "Export and handoff",
            "time_limit_min": 3,
            "instructions": "Export the current risk table to CSV and generate a printable cohort summary.",
            "response_type": "completion",
            "requires_cases": [],
        },
    ]

    payload = {
        "schema_version": "2.0",
        "default_analytic_year": year,
        "case_selection": selection_meta,
        "manipulation_catalog": {
            "correct": "Faithful outreach recommendation matching operational priority rule",
            "M2": "Incorrect outreach recommendation vs operational priority rule",
            "M3": "Unsupported grounded narrative claim contradicting record",
            "M4": "Incorrect NL query chronic filter",
            "M6": "Incorrect NL query time window on interpretation card",
            "M7": "Omitted utilization threshold on interpretation card",
        },
        "priority_rule": {
            "description": PRIORITY_RULE_DESCRIPTION,
            "weights": PRIORITY_RULE_WEIGHTS,
        },
        "comprehension": {
            "pass_threshold": 2,
            "questions": [
                {
                    "question_id": "Q1",
                    "prompt": "Which signal receives the highest weight in the outreach priority rule?",
                    "choices": [
                        "Inpatient claims",
                        "Outpatient claims only",
                        "Beneficiary age",
                        "State code",
                    ],
                    "correct_index": 0,
                },
                {
                    "question_id": "Q2",
                    "prompt": "When two cases tie on utilization signals, what should you consult next?",
                    "choices": [
                        "Chronic condition burden and total claims in the analytic year",
                        "Beneficiary name alphabetically",
                        "Random selection",
                        "Model version number",
                    ],
                    "correct_index": 0,
                },
                {
                    "question_id": "Q3",
                    "prompt": "Before accepting an AI outreach recommendation you should:",
                    "choices": [
                        "Compare it against the priority rule and visible record fields",
                        "Always accept the top model score",
                        "Ignore chronic flags",
                        "Skip verification when the interface looks confident",
                    ],
                    "correct_index": 0,
                },
            ],
        },
        "comprehension_study2": {
            "pass_threshold": 2,
            "questions": [
                {
                    "question_id": "S2Q1",
                    "prompt": "Before a search request is run you should:",
                    "choices": [
                        "Read the interpretation card and confirm, reject, or revise it",
                        "Assume the first result is correct",
                        "Skip the card if the wording looks fluent",
                        "Change the risk model",
                    ],
                    "correct_index": 0,
                },
                {
                    "question_id": "S2Q2",
                    "prompt": "How can you check a written summary claim?",
                    "choices": [
                        "Open the linked source field and compare it with the record",
                        "Trust any sentence that names a chronic condition",
                        "Use only the risk percentage",
                        "Ask the facilitator for the answer",
                    ],
                    "correct_index": 0,
                },
                {
                    "question_id": "S2Q3",
                    "prompt": "If a system output looks wrong you should:",
                    "choices": [
                        "Reject or revise it and verify against visible data",
                        "Accept it to save time",
                        "Ignore the record panels",
                        "Assume later tasks will correct it",
                    ],
                    "correct_index": 0,
                },
            ],
        },
        "case_sets": {
            "alpha": list(alpha_map.keys()),
            "beta": list(beta_map.keys()),
        },
        "cases": cases,
        "tasks": tasks,
        "task_sets": {
            "study1": [
                "S1-T0",
                "S1-T1",
                "S1-T2",
                "S1-T3",
                "S1-T4a",
                "S1-T4b",
                "S1-T5",
                "S1-T6",
            ],
            "study2": [
                "S2-T0",
                "S2-T1",
                "S2-T2",
                "S2-T3",
                "S2-T4",
                "S2-T5",
                "S2-T6",
                "S2-T7",
            ],
        },
    }

    output = REPO_ROOT / "study" / "study_cases.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {output} ({len(cases)} cases, {len(tasks)} tasks)")


if __name__ == "__main__":
    main()
