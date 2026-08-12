from __future__ import annotations

import hashlib
import uuid
from typing import Dict, List, Optional, Sequence

from hc_analytics.config import Settings, get_settings
from hc_analytics.study.loader import get_study_catalog, get_task_by_id
from hc_analytics.study.models import StudySessionResponse

STUDY1_OUTREACH_OUTCOMES = ("correct", "incorrect")
STUDY2_MANIPULATION_POOL = ("M3", "M4", "M6", "M7")
STUDY2_QUERY_POOL = ("M4", "M6", "M7")
CASE_SETS = ("alpha", "beta")
STUDY1_ORDERS: Sequence[Sequence[str]] = (("baseline", "xai"), ("xai", "baseline"))
STUDY2_ORDERS: Sequence[Sequence[str]] = (("baseline", "llm"), ("llm", "baseline"))


def _participant_digest(participant_id: str) -> int:
    return int(hashlib.sha256(participant_id.encode("utf-8")).hexdigest(), 16)


def assignment_plan(participant_id: str) -> Dict[str, object]:
    """Deterministic counterbalancing for condition order, case sets, and errors."""
    digest = _participant_digest(participant_id)
    study1_order = list(STUDY1_ORDERS[digest % 2])
    study2_order = list(STUDY2_ORDERS[(digest // 2) % 2])
    alpha_first = (digest // 4) % 2 == 0
    t2_index = (digest // 32) % len(STUDY2_QUERY_POOL)
    t6_index = (t2_index + 1) % len(STUDY2_QUERY_POOL)
    return {
        "study1_order": study1_order,
        "study2_order": study2_order,
        "case_set_first": "alpha" if alpha_first else "beta",
        "case_set_second": "beta" if alpha_first else "alpha",
        "study1_m2_on_first_block": (digest // 8) % 2 == 0,
        "s2_t2": STUDY2_QUERY_POOL[t2_index],
        "s2_t3": "M3" if (digest // 16) % 2 == 0 else "correct",
        "s2_t6": "correct" if (digest // 96) % 2 == 0 else STUDY2_QUERY_POOL[t6_index],
    }


def _study_order(plan: Dict[str, object], study: Optional[str], condition: Optional[str]) -> List[str]:
    if study == "study2" or condition == "llm":
        return list(plan["study2_order"])
    return list(plan["study1_order"])


def _block_index(condition: Optional[str], order: Sequence[str]) -> int:
    if condition is None:
        return 0
    try:
        return list(order).index(condition)
    except ValueError:
        return 0


def assign_case_set(
    participant_id: str,
    condition: Optional[str] = None,
    study: Optional[str] = None,
) -> str:
    plan = assignment_plan(participant_id)
    order = _study_order(plan, study, condition)
    index = _block_index(condition, order)
    return str(plan["case_set_first"] if index == 0 else plan["case_set_second"])


def study1_recommendation_is_manipulated(
    participant_id: str,
    condition: Optional[str] = None,
) -> bool:
    plan = assignment_plan(participant_id)
    order = list(plan["study1_order"])
    index = _block_index(condition, order)
    m2_on_first = bool(plan["study1_m2_on_first_block"])
    return m2_on_first if index == 0 else (not m2_on_first)


def assign_manipulations(
    participant_id: str,
    condition: Optional[str] = None,
) -> Dict[str, str]:
    plan = assignment_plan(participant_id)
    study1 = "M2" if study1_recommendation_is_manipulated(participant_id, condition) else "correct"
    return {
        "S1-T5": study1,
        "S2-T2": str(plan["s2_t2"]),
        "S2-T3": str(plan["s2_t3"]),
        "S2-T6": str(plan["s2_t6"]),
        "study1": study1,
        "study2": str(plan["s2_t2"]),
    }


def active_manipulations_for_task(
    participant_id: Optional[str],
    task_id: Optional[str],
    settings: Optional[Settings] = None,
    condition: Optional[str] = None,
) -> List[str]:
    runtime = settings or get_settings()
    if not runtime.study_mode or not participant_id or not task_id:
        return []

    assignments = assign_manipulations(participant_id, condition=condition)
    manipulation_id = assignments.get(task_id)
    if not manipulation_id:
        task = get_task_by_id(task_id, settings=runtime)
        if task is not None and task.manipulation_slot:
            manipulation_id = assignments.get(task.manipulation_slot)
    if not manipulation_id or manipulation_id == "correct":
        return []
    return [manipulation_id]


def new_trial_id() -> str:
    return str(uuid.uuid4())


def resolve_study_session(
    participant_id: str,
    settings: Optional[Settings] = None,
    condition: Optional[str] = None,
    study: Optional[str] = None,
) -> StudySessionResponse:
    runtime = settings or get_settings()
    catalog = get_study_catalog(settings=runtime)
    plan = assignment_plan(participant_id)
    assignments = assign_manipulations(participant_id, condition=condition)
    case_set = assign_case_set(participant_id, condition=condition, study=study)
    order = _study_order(plan, study, condition)
    case_set_by_condition = {
        cond: str(plan["case_set_first"] if index == 0 else plan["case_set_second"])
        for index, cond in enumerate(order)
    }
    cases = []
    manipulation_catalog: Dict[str, str] = {}
    task_sets: Dict[str, List[str]] = {}
    priority_rule: Dict[str, object] = {}
    comprehension: Dict[str, object] = {}
    if catalog is not None:
        manipulation_catalog = catalog.manipulation_catalog
        task_sets = catalog.task_sets
        priority_rule = catalog.priority_rule.model_dump()
        comprehension = catalog.comprehension
        allowed_ids = set(catalog.case_sets.get(case_set, []))
        for case in catalog.cases:
            if case.case_set not in {case_set, "shared"} and case.case_id not in allowed_ids:
                continue
            cases.append(
                {
                    "case_id": case.case_id,
                    "label": case.label,
                    "bene_id": case.bene_id,
                    "analytic_year": str(case.analytic_year),
                    "case_set": case.case_set,
                }
            )
    return StudySessionResponse(
        participant_id=participant_id,
        study_mode_enabled=runtime.study_mode,
        assignments=assignments,
        condition_order={"study1": list(plan["study1_order"]), "study2": list(plan["study2_order"])},
        manipulation_catalog=manipulation_catalog,
        task_sets=task_sets,
        cases=cases,
        case_set=case_set,
        case_set_by_condition=case_set_by_condition,
        recommended_first_condition=str(order[0]) if order else None,
        priority_rule=priority_rule,
        comprehension=comprehension,
    )
