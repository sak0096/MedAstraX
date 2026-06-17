from __future__ import annotations

import hashlib
import uuid
from typing import Dict, List, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.study.loader import get_study_catalog, get_task_by_id
from hc_analytics.study.models import StudySessionResponse

# Revised proposal Appendix D primary manipulations only.
STUDY1_MANIPULATION_POOL = ("M2",)
STUDY2_MANIPULATION_POOL = ("M3", "M4", "M6", "M7")
CASE_SETS = ("alpha", "beta")


def _participant_digest(participant_id: str) -> int:
    return int(hashlib.sha256(participant_id.encode("utf-8")).hexdigest(), 16)


def assign_case_set(participant_id: str) -> str:
    return CASE_SETS[_participant_digest(participant_id) % len(CASE_SETS)]


def assign_manipulations(participant_id: str) -> Dict[str, str]:
    digest = _participant_digest(participant_id)
    return {
        "study1": STUDY1_MANIPULATION_POOL[digest % len(STUDY1_MANIPULATION_POOL)],
        "study2": STUDY2_MANIPULATION_POOL[(digest // 3) % len(STUDY2_MANIPULATION_POOL)],
    }


def active_manipulations_for_task(
    participant_id: Optional[str],
    task_id: Optional[str],
    settings: Optional[Settings] = None,
) -> List[str]:
    runtime = settings or get_settings()
    if not runtime.study_mode or not participant_id or not task_id:
        return []

    task = get_task_by_id(task_id, settings=runtime)
    if task is None or task.manipulation_slot is None:
        return []

    assignments = assign_manipulations(participant_id)
    manipulation_id = assignments.get(task.manipulation_slot)
    if manipulation_id:
        return [manipulation_id]
    return []


def new_trial_id() -> str:
    return str(uuid.uuid4())


def resolve_study_session(
    participant_id: str,
    settings: Optional[Settings] = None,
) -> StudySessionResponse:
    runtime = settings or get_settings()
    catalog = get_study_catalog(settings=runtime)
    assignments = assign_manipulations(participant_id)
    case_set = assign_case_set(participant_id)
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
        manipulation_catalog=manipulation_catalog,
        task_sets=task_sets,
        cases=cases,
        case_set=case_set,
        priority_rule=priority_rule,
        comprehension=comprehension,
    )
