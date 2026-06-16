from __future__ import annotations

import hashlib
from typing import Dict, List, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.study.loader import get_study_catalog, get_task_by_id
from hc_analytics.study.models import StudySessionResponse

STUDY1_MANIPULATION_POOL = ("M1", "M2", "M5")
STUDY2_MANIPULATION_POOL = ("M2", "M3", "M4")


def assign_manipulations(participant_id: str) -> Dict[str, str]:
    digest = int(hashlib.sha256(participant_id.encode("utf-8")).hexdigest(), 16)
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


def resolve_study_session(
    participant_id: str,
    settings: Optional[Settings] = None,
) -> StudySessionResponse:
    runtime = settings or get_settings()
    catalog = get_study_catalog(settings=runtime)
    assignments = assign_manipulations(participant_id)
    cases = []
    manipulation_catalog: Dict[str, str] = {}
    task_sets: Dict[str, List[str]] = {}
    if catalog is not None:
        manipulation_catalog = catalog.manipulation_catalog
        task_sets = catalog.task_sets
        cases = [
            {
                "case_id": case.case_id,
                "label": case.label,
                "bene_id": case.bene_id,
                "analytic_year": str(case.analytic_year),
            }
            for case in catalog.cases
        ]
    return StudySessionResponse(
        participant_id=participant_id,
        study_mode_enabled=runtime.study_mode,
        assignments=assignments,
        manipulation_catalog=manipulation_catalog,
        task_sets=task_sets,
        cases=cases,
    )
