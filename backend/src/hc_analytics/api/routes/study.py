from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from hc_analytics.config import get_settings
from hc_analytics.instrumentation.events import EventType, StudyEvent, log_event
from hc_analytics.persistence.repository import (
    AttemptsExhausted,
    StateConflict,
    StudyRepository,
    StudyStoreError,
)
from hc_analytics.security.auth import assert_same_origin_mutation, require_admin
from hc_analytics.study.cohort_spec import cohort_ground_truth, cohort_spec_for_task
from hc_analytics.study.context import StudyRequestContext, get_study_context
from hc_analytics.study.loader import (
    get_case_by_id,
    get_study_catalog,
    get_task_by_id,
    tasks_for_study,
)
from hc_analytics.study.models import ComprehensionSubmission, TaskResponseSubmission
from hc_analytics.study.recommendations import (
    build_outreach_recommendation,
    outreach_case_ids_for_participant,
)
from hc_analytics.study.scoring import score_session_events
from hc_analytics.study.session import (
    active_manipulations_for_task,
    new_trial_id,
    resolve_study_session,
    study1_recommendation_is_manipulated,
)

router = APIRouter(prefix="/api/study", tags=["study"])


def _public_questions(bank: Dict[str, Any]) -> Dict[str, Any]:
    questions = []
    for question in bank.get("questions", []):
        questions.append({key: value for key, value in question.items() if key != "correct_index"})
    redacted = dict(bank)
    redacted["questions"] = questions
    return redacted


def _public_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    redacted = dict(payload)
    redacted["assignments"] = {}
    redacted["manipulation_catalog"] = {}
    redacted.pop("condition_order", None)
    redacted.pop("case_set_by_condition", None)
    redacted.pop("recommended_first_condition", None)
    redacted["comprehension"] = _public_questions(redacted.get("comprehension") or {})
    redacted["comprehension_study2"] = _public_questions(redacted.get("comprehension_study2") or {})
    return redacted


def _bound_session(request: Request) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    cookie = request.cookies.get("mx_session")
    if not cookie:
        if settings.strict_sessions:
            raise HTTPException(status_code=401, detail="A study session is required.")
        return None
    assert_same_origin_mutation(request.headers, required=settings.strict_sessions)
    try:
        session = StudyRepository.from_settings(settings).get_active_session(cookie)
    except StudyStoreError as error:
        raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
    if session is None:
        raise HTTPException(status_code=401, detail="A study session is required.")
    return session


def _participant_id(
    request: Request, supplied: Optional[str]
) -> tuple[Optional[Dict[str, Any]], str]:
    bound = _bound_session(request)
    if bound is not None:
        # A browser-supplied identifier is never authorization. The cookie's
        # server-side binding wins, even when a stale local-development header
        # is present.
        return bound, str(bound["participant_code"])
    if not supplied:
        raise HTTPException(status_code=422, detail="participant_id is required.")
    return None, supplied


def _public_recommendation(recommendation: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rule_description": recommendation.get("rule_description"),
        "case_ids": recommendation.get("case_ids", []),
        "recommended_ranking": recommendation.get("recommended_ranking", []),
        "rationale": recommendation.get("rationale"),
    }


def _public_task(task) -> Dict[str, Any]:
    return {
        "task_id": task.task_id,
        "study": task.study,
        "title": task.title,
        "time_limit_min": task.time_limit_min,
        "instructions": task.instructions,
        "response_type": task.response_type,
        "requires_cases": task.requires_cases,
        "conditions": task.conditions,
        "suggested_query": task.suggested_query,
        "sequential_judgment": task.sequential_judgment,
    }


def _validate_strict_response(
    task: Any,
    submission: TaskResponseSubmission,
    *,
    participant_id: str,
    condition: str,
    study: Optional[str],
) -> None:
    if len(json.dumps(submission.responses, default=str)) > 20_000:
        raise HTTPException(status_code=422, detail="Response is too large.")
    if submission.confidence is None:
        raise HTTPException(status_code=422, detail="Confidence is required.")
    if task.sequential_judgment and submission.phase not in {"initial", "final"}:
        raise HTTPException(
            status_code=422, detail="Sequential tasks require initial and final responses."
        )
    if not task.sequential_judgment and submission.phase != "single":
        raise HTTPException(status_code=422, detail="This task requires one final response.")

    if task.response_type in {"sequential_ranking", "ranking"}:
        expected = outreach_case_ids_for_participant(
            participant_id,
            settings=get_settings(),
            condition=condition,
            study=study or "study1",
        )
        ranking = submission.responses.get("ranking")
        if not isinstance(ranking, list) or len(ranking) != len(expected):
            raise HTTPException(status_code=422, detail="Ranking must include every assigned case.")
        if len(set(ranking)) != len(ranking) or set(ranking) != set(expected):
            raise HTTPException(
                status_code=422,
                detail="Ranking must be a permutation of assigned cases.",
            )
    elif task.response_type == "feature_list":
        drivers = submission.responses.get("drivers")
        if not isinstance(drivers, list) or len(drivers) != 3:
            raise HTTPException(status_code=422, detail="Exactly three risk factors are required.")
        features = [item.get("feature") for item in drivers if isinstance(item, dict)]
        directions = [item.get("direction") for item in drivers if isinstance(item, dict)]
        if len(features) != 3 or len(set(features)) != 3 or any(not item for item in features):
            raise HTTPException(status_code=422, detail="Risk factors must be distinct.")
        if any(item not in {"increases_risk", "decreases_risk"} for item in directions):
            raise HTTPException(status_code=422, detail="Each risk factor needs a direction.")
    elif task.response_type in {"cohort_selection", "beneficiary_list", "query_flow"}:
        result_count = submission.responses.get("result_count")
        if result_count is None or not isinstance(result_count, int) or result_count < 0:
            raise HTTPException(status_code=422, detail="A nonnegative result count is required.")
        top_bene_id = submission.responses.get("top_bene_id")
        if result_count > 0 and not str(top_bene_id or "").strip():
            raise HTTPException(status_code=422, detail="The top member ID is required.")
        result_ids = submission.responses.get("result_ids") or submission.responses.get(
            "beneficiary_ids"
        )
        if task.task_id == "S1-T2":
            if (
                not isinstance(result_ids, list)
                or len(result_ids) != 5
                or len(set(result_ids)) != 5
            ):
                raise HTTPException(
                    status_code=422, detail="Exactly five distinct member IDs are required."
                )
            if result_count != 5 or top_bene_id != result_ids[0]:
                raise HTTPException(
                    status_code=422,
                    detail="The count and top member must match the ranked five.",
                )
        elif isinstance(result_ids, list) and len(result_ids) != result_count:
            raise HTTPException(
                status_code=422, detail="The result count must match the submitted IDs."
            )
        if task.task_id == "S2-T6" and submission.responses.get("confirmation_action") not in {
            "confirm",
            "revise",
            "reject",
        }:
            raise HTTPException(
                status_code=422, detail="A confirm, revise, or reject decision is required."
            )
    elif task.response_type == "sequential_claim_review":
        designation = submission.responses.get("supported")
        if designation not in {"supported", "not_supported", "insufficient_information"}:
            raise HTTPException(status_code=422, detail="A follow-up designation is required.")
        if submission.phase == "final":
            if submission.responses.get("decision_action") not in {"keep", "change"}:
                raise HTTPException(
                    status_code=422, detail="A keep or change decision is required."
                )
            if not str(submission.responses.get("decision_reason") or "").strip():
                raise HTTPException(status_code=422, detail="A decision reason is required.")
            assessments = submission.responses.get("claim_assessments")
            if condition == "llm" and (
                not isinstance(assessments, list)
                or not assessments
                or any(
                    not isinstance(item, dict)
                    or item.get("designation")
                    not in {
                        "supported_by_linked_data",
                        "not_supported",
                        "cannot_determine",
                    }
                    for item in assessments
                )
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Classify each displayed claim using the linked-data choices.",
                )
    if task.response_type in {"sequential_ranking", "ranking"} and submission.phase == "final":
        if submission.responses.get("decision_action") not in {"keep", "revise"}:
            raise HTTPException(status_code=422, detail="A keep or revise decision is required.")
        support = submission.responses.get("recommendation_support")
        if not isinstance(support, int) or support < 1 or support > 7:
            raise HTTPException(
                status_code=422, detail="Recommendation support must be from 1 to 7."
            )
        if not str(submission.responses.get("decision_reason") or "").strip():
            raise HTTPException(status_code=422, detail="A decision reason is required.")


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
    request: Request,
    participant_id: Optional[str] = Query(default=None, min_length=1, max_length=64),
    facilitator: bool = Query(default=False),
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    del facilitator  # Public facilitator mode is not an authorization path.
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    bound, resolved_id = _participant_id(request, participant_id)
    condition = (
        bound["condition"] if bound is not None and bound.get("condition") else study_ctx.condition
    )
    study = bound["study"] if bound is not None else study_ctx.study
    payload = resolve_study_session(
        resolved_id,
        settings=settings,
        condition=condition,
        study=study,
    ).model_dump()
    return _public_session(payload)


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
    request: Request,
    participant_id: Optional[str] = Query(default=None, min_length=1, max_length=64),
    session_id: str = Query(default="legacy-session", min_length=8, max_length=128),
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    bound, participant_id = _participant_id(request, participant_id)
    if bound is not None:
        if bound["stage"] in {
            "comprehension_failed",
            "withdrawn",
            "technical_stop",
            "complete",
            "deleted",
        }:
            raise HTTPException(
                status_code=409, detail="Research tasks are closed for this session."
            )
        if task.response_type != "comprehension" and bound["stage"] in {
            "launched",
            "tutorial",
            "comprehension",
        }:
            raise HTTPException(status_code=409, detail="Research tasks are not open.")
        if task.study != bound["study"]:
            raise HTTPException(
                status_code=403, detail="This task is not part of the assigned study."
            )
        try:
            repository = StudyRepository.from_settings(settings)
            if task.response_type != "comprehension":
                catalog = get_study_catalog(settings=settings)
                repository.assert_task_available(
                    bound["enrollment_id"],
                    task_id,
                    list(catalog.task_sets[bound["study"]]) if catalog else [],
                )
            trial_from_store = repository.open_trial(
                enrollment_id=bound["enrollment_id"],
                session_hash=bound["session_hash"],
                task_id=task_id,
            )
        except StateConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except StudyStoreError as error:
            raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
    else:
        trial_from_store = None
    session = resolve_study_session(
        participant_id,
        settings=settings,
        condition=bound["condition"]
        if bound is not None and bound.get("condition")
        else study_ctx.condition,
        study=bound["study"] if bound is not None else study_ctx.study,
    )
    condition = (
        bound["condition"] if bound is not None and bound.get("condition") else study_ctx.condition
    )
    study_name = bound["study"] if bound is not None else study_ctx.study
    if bound is not None and bound.get("error_slots"):
        slot_key = task.manipulation_slot or task_id
        slot = bound["error_slots"].get(task_id) or bound["error_slots"].get(slot_key)
        active_manipulation = None if slot in {None, "correct"} else slot
    else:
        active = active_manipulations_for_task(
            participant_id,
            task_id,
            settings=settings,
            condition=condition,
        )
        active_manipulation = active[0] if active else None

    outreach_case_ids = []
    if task.response_type in {"sequential_ranking", "ranking"}:
        outreach_case_ids = outreach_case_ids_for_participant(
            participant_id,
            settings=settings,
            condition=condition,
            study=study_name or "study1",
        )

    trial_id = trial_from_store or (new_trial_id() if task.sequential_judgment else None)
    recommendation_correctness = None
    if task.task_id == "S1-T5" or task.manipulation_slot == "study1":
        recommendation_correctness = "incorrect" if active_manipulation == "M2" else "faithful"

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
                    "condition": condition,
                },
            )
        )

    case_ids = task.requires_cases or outreach_case_ids
    return {
        "task": _public_task(task),
        "trial_id": trial_id,
        "outreach_case_ids": outreach_case_ids,
        "cases": [case for case in session.cases if case["case_id"] in case_ids],
        "case_set": session.case_set,
    }


@router.get("/tasks/{task_id}/recommendation")
def outreach_recommendation(
    task_id: str,
    request: Request,
    participant_id: Optional[str] = Query(default=None, min_length=1, max_length=64),
    trial_id: Optional[str] = Query(default=None),
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    bound, participant_id = _participant_id(request, participant_id)
    condition = (
        bound["condition"] if bound is not None and bound.get("condition") else study_ctx.condition
    )
    study_name = bound["study"] if bound is not None else study_ctx.study
    if bound is not None and settings.strict_sessions:
        if not trial_id:
            raise HTTPException(
                status_code=409, detail="Submit the initial answer before assistance is shown."
            )
        repository = StudyRepository.from_settings(settings)
        if repository.get_trial_for_enrollment(trial_id, bound["enrollment_id"]) is None:
            raise HTTPException(status_code=404, detail="Unknown trial.")
        if repository.get_response(trial_id, "initial") is None:
            raise HTTPException(
                status_code=409, detail="Submit the initial answer before assistance is shown."
            )
        slot = (bound.get("error_slots") or {}).get(task_id) or (
            bound.get("error_slots") or {}
        ).get("study1")
        manipulated = slot == "M2"
    else:
        manipulated = study1_recommendation_is_manipulated(participant_id, condition)

    case_ids = outreach_case_ids_for_participant(
        participant_id,
        settings=settings,
        condition=condition,
        study=study_name or "study1",
    )
    if not case_ids:
        raise HTTPException(status_code=404, detail="No outreach cases assigned.")

    recommendation = build_outreach_recommendation(
        case_ids,
        manipulated=manipulated,
        settings=settings,
    )
    return _public_recommendation(recommendation)


@router.post("/tasks/{task_id}/response")
def submit_task_response(
    task_id: str,
    submission: TaskResponseSubmission,
    request: Request,
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    task = get_task_by_id(task_id, settings=settings)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Unknown task: {task_id}")

    bound, participant_id = _participant_id(request, submission.participant_id)
    submission.participant_id = participant_id
    condition = (
        bound["condition"] if bound is not None and bound.get("condition") else study_ctx.condition
    )
    if bound is not None and settings.strict_sessions:
        _validate_strict_response(
            task,
            submission,
            participant_id=participant_id,
            condition=condition,
            study=bound["study"],
        )
        if not submission.trial_id:
            raise HTTPException(status_code=409, detail="Trial is not part of this enrollment.")
        repository = StudyRepository.from_settings(settings)
        trial = repository.get_trial_for_enrollment(submission.trial_id, bound["enrollment_id"])
        if trial is None or trial["task_id"] != task_id:
            raise HTTPException(status_code=404, detail="Unknown trial.")
        if (
            submission.phase == "final"
            and repository.get_response(submission.trial_id, "initial") is None
        ):
            raise HTTPException(status_code=409, detail="The initial answer is not locked.")
        try:
            stored = repository.save_response(
                enrollment_id=bound["enrollment_id"],
                trial_id=submission.trial_id,
                task_id=task_id,
                phase=submission.phase,
                payload=submission.responses,
                confidence=submission.confidence,
            )
        except StateConflict as error:
            raise HTTPException(
                status_code=409, detail="The initial answer is already locked."
            ) from error
        except StudyStoreError as error:
            raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
        if submission.phase in {"single", "final"}:
            catalog = get_study_catalog(settings=settings)
            if catalog is not None:
                repository.close_task_block_if_complete(
                    bound["enrollment_id"], list(catalog.task_sets[bound["study"]])
                )
        if stored.get("idempotent") and submission.phase == "initial":
            return {
                "stored": True,
                "task_id": task_id,
                "phase": submission.phase,
                "idempotent": True,
            }
    if bound is not None and bound.get("error_slots"):
        slot = bound["error_slots"].get(task_id) or bound["error_slots"].get(
            task.manipulation_slot or ""
        )
        active = [] if slot in {None, "correct"} else [slot]
    else:
        active = active_manipulations_for_task(
            submission.participant_id,
            task_id,
            settings=settings,
            condition=condition,
        )
    active_manipulation = active[0] if active else None
    manipulated_outreach = active_manipulation == "M2" or (
        active_manipulation is None
        and study1_recommendation_is_manipulated(submission.participant_id, condition)
        and (bound is None or not bound.get("error_slots"))
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
    elif task.response_type == "feature_list":
        case_id = (task.requires_cases or [None])[0]
        case = get_case_by_id(case_id, settings=settings) if case_id else None
        if case is not None:
            ground_truth = {
                "expected_drivers": case.ground_truth.get("top_hospitalization_features", [])[:3],
            }
    elif task.response_type == "sequential_claim_review" and submission.phase == "final":
        case_id = (task.requires_cases or [None])[0]
        case = get_case_by_id(case_id, settings=settings) if case_id else None
        m3 = (case.manipulations.get("M3") if case else None) or {}
        ground_truth = {
            "unsupported_statement": m3.get("statement"),
            "manipulated": active_manipulation == "M3",
        }
    elif task.response_type in {"query_flow", "cohort_selection", "beneficiary_list"}:
        # Ground truth is defined by the frozen task, never by participant- or
        # manipulation-controlled execution parameters submitted in the response.
        params = cohort_spec_for_task(task.task_id, settings=settings)
        ground_truth = cohort_ground_truth(params, settings=settings)
        ground_truth["manipulated"] = bool(active)
        ground_truth["manipulation_type"] = active_manipulation

    timed_out = False
    if submission.time_ms is not None and task.time_limit_min:
        timed_out = submission.time_ms > task.time_limit_min * 60 * 1000

    event_type = (
        EventType.TASK_INITIAL_RESPONSE
        if submission.phase == "initial"
        else EventType.TASK_RESPONSE
    )

    payload = {
        "responses": submission.responses,
        "time_ms": submission.time_ms,
        "timed_out": timed_out,
        "time_limit_min": task.time_limit_min,
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
        "condition": condition,
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

    canonical = bound is not None and settings.strict_sessions
    return {
        "stored": True if canonical else settings.log_events,
        "task_id": task_id,
        "phase": submission.phase,
    }


@router.post("/comprehension")
def submit_comprehension(
    submission: ComprehensionSubmission,
    request: Request,
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    catalog = get_study_catalog(settings=settings)
    if catalog is None:
        raise HTTPException(status_code=503, detail="Study catalog not loaded.")

    bound, participant_id = _participant_id(request, submission.participant_id)
    submission.participant_id = participant_id
    study_arm = (
        (bound["study"] if bound is not None else None)
        or submission.study
        or study_ctx.study
        or "study1"
    )
    bank = (
        catalog.comprehension_study2
        if study_arm == "study2" and catalog.comprehension_study2
        else catalog.comprehension
    )
    questions = bank.get("questions", [])
    correct = 0
    results = []
    for question in questions:
        qid = question["question_id"]
        selected = submission.answers.get(qid)
        is_correct = selected == question["correct_index"]
        if is_correct:
            correct += 1
        results.append({"question_id": qid, "correct": is_correct})

    threshold = int(bank.get("pass_threshold", len(questions)))
    passed = correct >= threshold

    if settings.log_events:
        log_event(
            StudyEvent(
                event_type=EventType.COMPREHENSION_COMPLETE,
                participant_id=submission.participant_id,
                session_id=submission.session_id,
                payload={
                    "correct": correct,
                    "passed": passed,
                    "results": results,
                    "study": study_arm,
                },
            )
        )

    attempt_number = None
    research_tasks_ended = False
    if bound is not None and settings.strict_sessions:
        try:
            import hashlib
            import json as json_lib

            answer_key = (
                submission.idempotency_key
                or hashlib.sha256(
                    json_lib.dumps(
                        {
                            "answers": submission.answers,
                            "study": study_arm,
                            "enrollment": bound["enrollment_id"],
                        },
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()
            )
            recorded = StudyRepository.from_settings(settings).record_comprehension(
                enrollment_id=bound["enrollment_id"],
                study=study_arm,
                idempotency_key=answer_key,
                correct_count=correct,
                question_count=len(questions),
                passed=passed,
            )
        except AttemptsExhausted as error:
            raise HTTPException(
                status_code=409, detail="Comprehension retries are exhausted."
            ) from error
        except StudyStoreError as error:
            raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
        attempt_number = recorded["attempt_number"]
        passed = recorded["passed"]
        correct = recorded["correct_count"]
        research_tasks_ended = recorded["research_tasks_ended"]

    return {
        "passed": passed,
        "correct": correct,
        "total": len(questions),
        "results": results,
        "study": study_arm,
        "attempt_number": attempt_number,
        "research_tasks_ended": research_tasks_ended,
        "payment_amount_cents": None,
        "exit_reason": "comprehension_failed_before_tasks" if research_tasks_ended else None,
    }


@router.post("/score-session")
def score_session(
    session_id: str,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    settings = get_settings()
    if settings.research_admin_required:
        require_admin(authorization)
    if not settings.study_mode:
        raise HTTPException(status_code=404, detail="Study mode is disabled.")
    from hc_analytics.instrumentation.store import load_session_events

    events = load_session_events(session_id, settings=settings)
    return score_session_events(events)
