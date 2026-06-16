from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from hc_analytics.config import get_settings
from hc_analytics.instrumentation.events import EventType, StudyEvent, log_event
from hc_analytics.study.loader import get_study_catalog, get_task_by_id, tasks_for_study
from hc_analytics.study.models import TaskResponseSubmission
from hc_analytics.study.session import resolve_study_session

router = APIRouter(prefix="/api/study", tags=["study"])


def _public_task(task) -> Dict[str, Any]:
    return {
        "task_id": task.task_id,
        "study": task.study,
        "title": task.title,
        "time_limit_min": task.time_limit_min,
        "instructions": task.instructions,
        "response_type": task.response_type,
        "requires_cases": task.requires_cases,
        "manipulation_slot": task.manipulation_slot,
        "conditions": task.conditions,
        "suggested_query": task.suggested_query,
    }


@router.get("/meta")
def study_meta() -> Dict[str, Any]:
    settings = get_settings()
    catalog = get_study_catalog(settings=settings)
    return {
        "study_mode_enabled": settings.study_mode,
        "catalog_loaded": catalog is not None,
        "schema_version": catalog.schema_version if catalog else None,
        "default_analytic_year": catalog.default_analytic_year if catalog else None,
        "case_count": len(catalog.cases) if catalog else 0,
        "task_count": len(catalog.tasks) if catalog else 0,
        "task_sets": catalog.task_sets if catalog else {},
    }


@router.get("/session")
def study_session(participant_id: str = Query(min_length=1, max_length=64)) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    return resolve_study_session(participant_id, settings=settings).model_dump()


@router.get("/tasks")
def list_tasks(
    study: Optional[str] = Query(default=None, pattern="^(study1|study2)$"),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    catalog = get_study_catalog(settings=settings)
    if catalog is None:
        raise HTTPException(status_code=503, detail="Study catalog not loaded.")

    if study:
        selected = tasks_for_study(study, settings=settings)
    else:
        selected = catalog.tasks
    return {
        "tasks": [_public_task(task) for task in selected],
        "task_sets": catalog.task_sets,
    }


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")
    return _public_task(task)


@router.post("/tasks/{task_id}/start")
def start_task(
    task_id: str,
    participant_id: str = Query(min_length=1, max_length=64),
    session_id: str = Query(min_length=8, max_length=128),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    session = resolve_study_session(participant_id, settings=settings)
    active_manipulation = None
    if task.manipulation_slot:
        active_manipulation = session.assignments.get(task.manipulation_slot)

    if settings.log_events:
        log_event(
            StudyEvent(
                event_type=EventType.TASK_START,
                participant_id=participant_id,
                session_id=session_id,
                task_id=task_id,
                payload={
                    "study": task.study,
                    "active_manipulation": active_manipulation,
                    "requires_cases": task.requires_cases,
                },
            )
        )

    return {
        "task": _public_task(task),
        "active_manipulation": active_manipulation,
        "cases": [
            case
            for case in session.cases
            if case["case_id"] in task.requires_cases
        ],
    }


@router.post("/tasks/{task_id}/response")
def submit_task_response(task_id: str, submission: TaskResponseSubmission) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    session = resolve_study_session(submission.participant_id, settings=settings)
    active_manipulation = None
    if task.manipulation_slot:
        active_manipulation = session.assignments.get(task.manipulation_slot)

    payload = {
        "responses": submission.responses,
        "time_ms": submission.time_ms,
        "notes": submission.notes,
        "study": task.study,
        "response_type": task.response_type,
        "active_manipulation": active_manipulation,
    }

    if settings.log_events:
        log_event(
            StudyEvent(
                event_type=EventType.TASK_RESPONSE,
                participant_id=submission.participant_id,
                session_id=submission.session_id,
                task_id=task_id,
                payload=payload,
            )
        )

    return {"stored": settings.log_events, "task_id": task_id}
