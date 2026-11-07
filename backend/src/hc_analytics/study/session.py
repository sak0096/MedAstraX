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
    # Target ~20–30% errors across Study 2 primary slots (T2/T3/T6).
    t2_error = (digest // 64) % 4 == 0
    t3_error = (digest // 16) % 4 == 0
    t6_error = (digest // 96) % 4 == 0
    return {
        "study1_order": study1_order,
        "study2_order": study2_order,
        "case_set_first": "alpha" if alpha_first else "beta",
        "case_set_second": "beta" if alpha_first else "alpha",
        "study1_m2_on_first_block": (digest // 8) % 2 == 0,
        "s2_t2": STUDY2_QUERY_POOL[t2_index] if t2_error else "correct",
        "s2_t3": "M3" if t3_error else "correct",
        "s2_t6": STUDY2_QUERY_POOL[t6_index] if t6_error else "correct",
    }


def blocked_assignment_plan(
    participant_id: str,
    *,
    study: str,
    study_slot: int,
) -> Dict[str, object]:
    """Apply a reproducible four-cell block without changing error mappings.

    The existing participant-derived plan remains the source for prespecified
    error slots. Only condition order and alpha/beta parallel-case order are
    balanced by the enrollment's one-based slot within its study.
    """
    if study not in {"study1", "study2"}:
        raise ValueError(f"Unknown study: {study}")
    if study_slot < 1:
        raise ValueError("study_slot must be one-based.")
    plan = assignment_plan(participant_id)
    cell = (study_slot - 1) % 4
    order_index = cell % 2
    alpha_first = cell < 2
    order_key = "study1_order" if study == "study1" else "study2_order"
    orders = STUDY1_ORDERS if study == "study1" else STUDY2_ORDERS
    plan[order_key] = list(orders[order_index])
    plan["case_set_first"] = "alpha" if alpha_first else "beta"
    plan["case_set_second"] = "beta" if alpha_first else "alpha"
    plan["assignment_block"] = (study_slot - 1) // 4
    plan["assignment_cell"] = cell
    return plan


def validate_assignment_design(
    *,
    per_study: int = 60,
    settings: Optional[Settings] = None,
) -> Dict[str, object]:
    """Validate balance and internal consistency of the existing frozen map."""
    if per_study < 1:
        raise ValueError("per_study must be positive.")
    catalog = get_study_catalog(settings=settings or get_settings())
    if catalog is None:
        raise ValueError("Study catalog is unavailable.")
    known_cases = {case.case_id for case in catalog.cases}
    alpha = set(catalog.case_sets.get("alpha", []))
    beta = set(catalog.case_sets.get("beta", []))
    if not alpha or not beta or alpha & beta or not (alpha | beta) <= known_cases:
        raise ValueError("The existing alpha/beta parallel-case map is inconsistent.")
    expected_fixed_cases = {"S1-T3": "B-07", "S2-T3": "B-15"}
    for task_id, case_id in expected_fixed_cases.items():
        task = get_task_by_id(task_id, settings=settings or get_settings())
        if task is None or task.requires_cases != [case_id]:
            raise ValueError(f"The existing reviewed-source mapping changed for {task_id}.")
    allowed_manipulations = set(catalog.manipulation_catalog)
    for case in catalog.cases:
        unknown = set(case.manipulations) - allowed_manipulations
        if unknown:
            raise ValueError(f"Unknown manipulation IDs on {case.case_id}: {sorted(unknown)}")

    studies: Dict[str, object] = {}
    for study, order_key in (("study1", "study1_order"), ("study2", "study2_order")):
        order_counts: Dict[str, int] = {}
        case_first_counts = {"alpha": 0, "beta": 0}
        cells = [0, 0, 0, 0]
        for slot in range(1, per_study + 1):
            plan = blocked_assignment_plan(
                f"VALIDATE-{study}-{slot:03d}",
                study=study,
                study_slot=slot,
            )
            order = "→".join(str(item) for item in plan[order_key])
            order_counts[order] = order_counts.get(order, 0) + 1
            case_first_counts[str(plan["case_set_first"])] += 1
            cells[int(plan["assignment_cell"])] += 1
        if max(order_counts.values()) - min(order_counts.values()) > 1:
            raise ValueError(f"Condition order is not balanced for {study}.")
        if max(case_first_counts.values()) - min(case_first_counts.values()) > 1:
            raise ValueError(f"Parallel-case order is not balanced for {study}.")
        if max(cells) - min(cells) > 1:
            raise ValueError(f"Four-cell blocked assignment is not balanced for {study}.")
        studies[study] = {
            "condition_order_counts": order_counts,
            "case_set_first_counts": case_first_counts,
            "four_cell_counts": cells,
        }
    return {
        "per_study": per_study,
        "studies": studies,
        "fixed_case_mapping": expected_fixed_cases,
        "allowed_manipulations": sorted(allowed_manipulations),
    }


def _study_order(
    plan: Dict[str, object], study: Optional[str], condition: Optional[str]
) -> List[str]:
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
        condition_order={
            "study1": list(plan["study1_order"]),
            "study2": list(plan["study2_order"]),
        },
        manipulation_catalog=manipulation_catalog,
        task_sets=task_sets,
        cases=cases,
        case_set=case_set,
        case_set_by_condition=case_set_by_condition,
        recommended_first_condition=str(order[0]) if order else None,
        priority_rule=priority_rule,
        comprehension=comprehension,
        comprehension_study2=catalog.comprehension_study2 if catalog is not None else {},
    )
