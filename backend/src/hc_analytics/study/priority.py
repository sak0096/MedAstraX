"""Operational outreach priority rule for Study 1 ground truth."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

PRIORITY_RULE_WEIGHTS: Dict[str, float] = {
    "inpatient_claims": 3.0,
    "outpatient_claims": 0.5,
    "chronic_condition_count": 2.0,
    "total_claims": 0.1,
}

PRIORITY_RULE_DESCRIPTION = (
    "Rank outreach candidates using the study operational priority rule: "
    "3 points per inpatient claim, 0.5 per outpatient claim, "
    "2 points per chronic condition flag, and 0.1 per total claim in the analytic year. "
    "Higher score = higher outreach priority."
)


def compute_priority_score(record: Mapping[str, Any]) -> float:
    score = 0.0
    for field, weight in PRIORITY_RULE_WEIGHTS.items():
        value = record.get(field)
        if value is None:
            continue
        score += float(value) * weight
    return round(score, 4)


def rank_case_ids(
    case_ids: Sequence[str],
    *,
    case_records: Mapping[str, Mapping[str, Any]],
) -> List[str]:
    scored = [
        (case_id, compute_priority_score(case_records[case_id]))
        for case_id in case_ids
        if case_id in case_records
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return [case_id for case_id, _ in scored]


def incorrect_recommendation_ranking(correct_ranking: Sequence[str]) -> List[str]:
    """Promote the lowest-priority case to rank 1 (primary Study 1 error)."""
    if len(correct_ranking) < 2:
        return list(correct_ranking)
    manipulated = list(correct_ranking)
    lowest = manipulated[-1]
    manipulated.remove(lowest)
    manipulated.insert(0, lowest)
    return manipulated
