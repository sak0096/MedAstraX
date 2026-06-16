from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.study.models import StudyCaseDefinition, StudyCatalog, StudyTaskDefinition

_CATALOG: Optional[StudyCatalog] = None


def study_cases_path(settings: Optional[Settings] = None) -> Path:
    runtime = settings or get_settings()
    return runtime.repo_root / runtime.study_cases_path


def load_study_catalog(settings: Optional[Settings] = None) -> StudyCatalog:
    path = study_cases_path(settings)
    if not path.exists():
        raise FileNotFoundError(f"Study catalog not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return StudyCatalog.model_validate(payload)


@lru_cache(maxsize=1)
def _cached_catalog(path_str: str, mtime_ns: int) -> StudyCatalog:
    _ = mtime_ns
    return StudyCatalog.model_validate(json.loads(Path(path_str).read_text(encoding="utf-8")))


def get_study_catalog(settings: Optional[Settings] = None) -> Optional[StudyCatalog]:
    runtime = settings or get_settings()
    if not runtime.study_mode:
        return None
    path = study_cases_path(runtime)
    if not path.exists():
        return None
    return _cached_catalog(str(path), path.stat().st_mtime_ns)


def get_case_by_id(case_id: str, settings: Optional[Settings] = None) -> Optional[StudyCaseDefinition]:
    catalog = get_study_catalog(settings)
    if catalog is None:
        return None
    for case in catalog.cases:
        if case.case_id == case_id:
            return case
    return None


def get_case_for_beneficiary(
    bene_id: str,
    analytic_year: Optional[int] = None,
    settings: Optional[Settings] = None,
) -> Optional[StudyCaseDefinition]:
    catalog = get_study_catalog(settings)
    if catalog is None:
        return None
    for case in catalog.cases:
        if case.bene_id != bene_id:
            continue
        if analytic_year is not None and case.analytic_year != analytic_year:
            continue
        return case
    return None


def get_task_by_id(task_id: str, settings: Optional[Settings] = None) -> Optional[StudyTaskDefinition]:
    catalog = get_study_catalog(settings)
    if catalog is None:
        return None
    for task in catalog.tasks:
        if task.task_id == task_id:
            return task
    return None


def tasks_for_study(study: str, settings: Optional[Settings] = None) -> List[StudyTaskDefinition]:
    catalog = get_study_catalog(settings)
    if catalog is None:
        return []
    task_ids = catalog.task_sets.get(study, [])
    by_id = {task.task_id: task for task in catalog.tasks}
    return [by_id[task_id] for task_id in task_ids if task_id in by_id]


def case_lookup_map(settings: Optional[Settings] = None) -> Dict[str, StudyCaseDefinition]:
    catalog = get_study_catalog(settings)
    if catalog is None:
        return {}
    return {case.case_id: case for case in catalog.cases}
