"""Outreach AI recommendation payloads for Study 1 reliance trials."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from hc_analytics.config import Settings, get_settings
from hc_analytics.study.loader import get_case_by_id, get_study_catalog
from hc_analytics.study.priority import (
    PRIORITY_RULE_DESCRIPTION,
    compute_priority_score,
    incorrect_recommendation_ranking,
    rank_case_ids,
)


def _case_priority_record(case_id: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    case = get_case_by_id(case_id, settings=settings)
    if case is None:
        raise ValueError(f"Unknown case: {case_id}")
    ground_truth = dict(case.ground_truth)
    if "priority_score" not in ground_truth:
        ground_truth["priority_score"] = compute_priority_score(ground_truth)
    return ground_truth


def build_outreach_recommendation(
    case_ids: Sequence[str],
    *,
    manipulated: bool,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    runtime = settings or get_settings()
    records = {case_id: _case_priority_record(case_id, settings=runtime) for case_id in case_ids}
    correct_ranking = rank_case_ids(case_ids, case_records=records)
    displayed_ranking = (
        incorrect_recommendation_ranking(correct_ranking) if manipulated else correct_ranking
    )
    return {
        "rule_description": PRIORITY_RULE_DESCRIPTION,
        "case_ids": list(case_ids),
        "priority_scores": {
            case_id: records[case_id].get("priority_score", compute_priority_score(records[case_id]))
            for case_id in case_ids
        },
        "correct_ranking": correct_ranking,
        "recommended_ranking": displayed_ranking,
        "manipulated": manipulated,
        "rationale": (
            "Model recommends prioritizing cases in the order shown based on utilization "
            "burden and chronic-condition signals."
        ),
    }


def outreach_case_ids_for_participant(
    participant_id: str,
    *,
    settings: Optional[Settings] = None,
) -> List[str]:
    from hc_analytics.study.session import assign_case_set

    runtime = settings or get_settings()
    catalog = get_study_catalog(settings=runtime)
    if catalog is None:
        return []
    case_set = assign_case_set(participant_id)
    return list(catalog.case_sets.get(case_set, []))
