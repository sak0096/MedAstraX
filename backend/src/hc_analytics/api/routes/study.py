from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from hc_analytics.config import get_settings
from hc_analytics.instrumentation.events import EventType, StudyEvent, log_event
from hc_analytics.study.context import StudyRequestContext, get_study_context
from hc_analytics.study.loader import get_study_catalog, get_task_by_id, tasks_for_study
from hc_analytics.study.models import ComprehensionSubmission, TaskResponseSubmission
from hc_analytics.study.recommendations import build_outreach_recommendation, outreach_case_ids_for_participant
from hc_analytics.study.scoring import score_session_events
from hc_analytics.study.session import (
    active_manipulations_for_task,
    new_trial_id,
    resolve_study_session,
    study1_recommendation_is_manipulated,
)

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
        "sequential_judgment": task.sequential_judgment,
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
        "case_sets": catalog.case_sets if catalog else {},
    }


@router.get("/session")
def study_session(
    participant_id: str = Query(min_length=1, max_length=64),
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    return resolve_study_session(
        participant_id,
        settings=settings,
        condition=study_ctx.condition,
        study=study_ctx.study,
    ).model_dump()


@router.get("/priority-rule")
def priority_rule() -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    catalog = get_study_catalog(settings=settings)
    if catalog is None:
        raise HTTPException(status_code=503, detail="Study catalog not loaded.")
    return catalog.priority_rule.model_dump()


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
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    session = resolve_study_session(
        participant_id,
        settings=settings,
        condition=study_ctx.condition,
        study=study_ctx.study,
    )
    active = active_manipulations_for_task(
        participant_id,
        task_id,
        settings=settings,
        condition=study_ctx.condition,
    )
    active_manipulation = active[0] if active else None

    outreach_case_ids = []
    if task.response_type in {"sequential_ranking", "ranking"}:
        outreach_case_ids = outreach_case_ids_for_participant(
            participant_id,
            settings=settings,
            condition=study_ctx.condition,
            study=study_ctx.study or "study1",
        )

    trial_id = new_trial_id() if task.sequential_judgment else None
    recommendation_correctness = None
    if task.task_id == "S1-T5" or task.manipulation_slot == "study1":
        recommendation_correctness = (
            "incorrect"
            if study1_recommendation_is_manipulated(participant_id, study_ctx.condition)
            else "faithful"
        )

    if settings.log_events:
        log_event(
            StudyEvent(
                event_type=EventType.TASK_START,
                participant_id=participant_id,
                session_id=session_id,
                task_id=task_id,
                condition=study_ctx.experimental_condition,
                payload={
                    "study": task.study,
                    "active_manipulation": active_manipulation,
                    "recommendation_correctness": recommendation_correctness,
                    "requires_cases": task.requires_cases or outreach_case_ids,
                    "trial_id": trial_id,
                    "sequential_judgment": task.sequential_judgment,
                    "case_set": session.case_set,
                    "condition": study_ctx.condition,
                },
            )
        )

    case_ids = task.requires_cases or outreach_case_ids
    return {
        "task": _public_task(task),
        "active_manipulation": active_manipulation,
        "recommendation_correctness": recommendation_correctness,
        "trial_id": trial_id,
        "outreach_case_ids": outreach_case_ids,
        "cases": [case for case in session.cases if case["case_id"] in case_ids],
        "case_set": session.case_set,
    }


@router.get("/tasks/{task_id}/recommendation")
def outreach_recommendation(
    task_id: str,
    participant_id: str = Query(min_length=1, max_length=64),
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    case_ids = outreach_case_ids_for_participant(
        participant_id,
        settings=settings,
        condition=study_ctx.condition,
        study=study_ctx.study or "study1",
    )
    if not case_ids:
        raise HTTPException(status_code=404, detail="No outreach cases assigned.")

    manipulated = study1_recommendation_is_manipulated(participant_id, study_ctx.condition)
    recommendation = build_outreach_recommendation(
        case_ids,
        manipulated=manipulated,
        settings=settings,
    )
    return recommendation


@router.post("/tasks/{task_id}/response")
def submit_task_response(
    task_id: str,
    submission: TaskResponseSubmission,
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    active = active_manipulations_for_task(
        submission.participant_id,
        task_id,
        settings=settings,
        condition=study_ctx.condition,
    )
    active_manipulation = active[0] if active else None
    manipulated_outreach = study1_recommendation_is_manipulated(
        submission.participant_id,
        study_ctx.condition,
    )

    ground_truth: Dict[str, Any] = {}
    if task.response_type in {"sequential_ranking", "ranking"} and submission.phase == "final":
        case_ids = outreach_case_ids_for_participant(
            submission.participant_id,
            settings=settings,
            condition=study_ctx.condition,
            study=study_ctx.study or "study1",
        )
        recommendation = build_outreach_recommendation(
            case_ids,
            manipulated=manipulated_outreach,
            settings=settings,
        )
        ground_truth = {
            "correct_ranking": recommendation["correct_ranking"],
            "recommendation_ranking": recommendation["recommended_ranking"],
            "manipulated": recommendation["manipulated"],
            "manipulation_type": "M2" if manipulated_outreach else "correct",
            "recommendation_correctness": "incorrect" if manipulated_outreach else "faithful",
        }

    event_type = (
        EventType.TASK_INITIAL_RESPONSE
        if submission.phase == "initial"
        else EventType.TASK_RESPONSE
    )

    payload = {
        "responses": submission.responses,
        "time_ms": submission.time_ms,
        "notes": submission.notes,
        "study": task.study,
        "response_type": task.response_type,
        "active_manipulation": active_manipulation,
        "phase": submission.phase,
        "trial_id": submission.trial_id,
        "confidence": submission.confidence,
        "reliance_source": submission.reliance_source,
        "ground_truth": ground_truth or None,
        "manipulated": ground_truth.get("manipulated") if ground_truth else bool(active),
        "manipulation_type": active_manipulation,
        "recommendation_correctness": (
            "incorrect"
            if task.task_id == "S1-T5" and manipulated_outreach
            else "faithful"
            if task.task_id == "S1-T5"
            else None
        ),
        "condition": study_ctx.condition,
    }

    if settings.log_events:
        log_event(
            StudyEvent(
                event_type=event_type,
                participant_id=submission.participant_id,
                session_id=submission.session_id,
                task_id=task_id,
                condition=study_ctx.experimental_condition,
                payload=payload,
            )
        )

    return {"stored": settings.log_events, "task_id": task_id, "phase": submission.phase}


@router.post("/comprehension")
def submit_comprehension(submission: ComprehensionSubmission) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    catalog = get_study_catalog(settings=settings)
    if catalog is None:
        raise HTTPException(status_code=503, detail="Study catalog not loaded.")

    questions = catalog.comprehension.get("questions", [])
    correct = 0
    results = []
    for question in questions:
        qid = question["question_id"]
        selected = submission.answers.get(qid)
        is_correct = selected == question["correct_index"]
        if is_correct:
            correct += 1
        results.append({"question_id": qid, "correct": is_correct})

    threshold = int(catalog.comprehension.get("pass_threshold", len(questions)))
    passed = correct >= threshold

    if settings.log_events:
        log_event(
            StudyEvent(
                event_type=EventType.COMPREHENSION_COMPLETE,
                participant_id=submission.participant_id,
                session_id=submission.session_id,
                payload={"correct": correct, "passed": passed, "results": results},
            )
        )

    return {"passed": passed, "correct": correct, "total": len(questions), "results": results}


@router.post("/score-session")
def score_session(session_id: str) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    from hc_analytics.instrumentation.store import load_session_events

    events = load_session_events(session_id, settings=settings)
    return score_session_events(events)
