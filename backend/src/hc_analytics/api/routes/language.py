from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from hc_analytics.config import get_settings
from hc_analytics.explainability.pipeline import load_cached_bundle
from hc_analytics.language.constants import LANGUAGE_SCHEMA_VERSION, SUPPORTED_QUERY_ACTIONS
from hc_analytics.language.corrections import (
    apply_correction,
    public_interpretation,
    public_parameters,
)
from hc_analytics.language.models import (
    GroundedSummaryResponse,
    InterpretedQuery,
    QueryExecuteRequest,
    QueryInterpretRequest,
    QueryResult,
)
from hc_analytics.language.provider import (
    active_provider_name,
    generate_grounded_summary,
    provider_configured,
)
from hc_analytics.language.query_cache import (
    load_interpretation,
    load_result,
    query_status,
    set_query_status,
    store_interpretation,
    store_result,
)
from hc_analytics.language.query_executor import execute_interpreted_query
from hc_analytics.language.query_parser import parse_natural_language_query
from hc_analytics.study.cohort_spec import study_analytic_year
from hc_analytics.study.context import StudyRequestContext, get_study_context
from hc_analytics.study.loader import get_case_for_beneficiary
from hc_analytics.study.manipulations import apply_query_manipulations, apply_summary_manipulations

router = APIRouter(prefix="/api/language", tags=["language"])


def _require_language_condition(study_ctx: StudyRequestContext) -> None:
    if study_ctx.study_mode and study_ctx.condition != "llm":
        raise HTTPException(
            status_code=404, detail="This panel is not part of the current session."
        )


class QueryCorrectionRequest(BaseModel):
    analytic_year: Optional[int] = None
    chronic_filter: Optional[str] = None
    min_total_claims: Optional[int] = None


def _correction_payload(body: QueryCorrectionRequest) -> Dict[str, Any]:
    provided = body.model_dump(exclude_unset=True)
    if not provided:
        raise HTTPException(status_code=400, detail="A correction needs at least one field.")
    return provided


def _explanations_ready() -> bool:
    return (get_settings().artifacts_path / "explanations" / "manifest.json").exists()


@router.get("/meta")
def language_meta() -> Dict[str, Any]:
    settings = get_settings()
    return {
        "schema_version": LANGUAGE_SCHEMA_VERSION,
        "language_ready": _explanations_ready(),
        "provider": active_provider_name(settings),
        "provider_configured": provider_configured(settings),
        "supported_actions": list(SUPPORTED_QUERY_ACTIONS),
        "requires_confirmation": True,
        "fallback_phrases": ["insufficient evidence"],
    }


@router.get("/summary/{bene_id}")
def grounded_summary(
    bene_id: str,
    analytic_year: Optional[int] = Query(default=None),
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> GroundedSummaryResponse:
    settings = get_settings()
    _require_language_condition(study_ctx)
    if settings.study_mode:
        if analytic_year is None:
            raise HTTPException(status_code=400, detail="Analytic year is required.")
        from hc_analytics.study.frozen import load_frozen_summary

        summary = load_frozen_summary(bene_id, analytic_year, settings=settings)
        if summary is None:
            raise HTTPException(status_code=503, detail="This record is temporarily unavailable.")
        if study_ctx.active_manipulations:
            case = get_case_for_beneficiary(bene_id, analytic_year, settings=settings)
            summary = apply_summary_manipulations(
                summary,
                case=case,
                active_manipulations=study_ctx.active_manipulations,
            )
        return summary
    if not _explanations_ready():
        raise HTTPException(
            status_code=503,
            detail="Explanations not available. Run `python -m hc_analytics.explainability` first.",
        )

    if analytic_year is None:
        from hc_analytics.api.routes.explanations import _load_local_topk

        frame = _load_local_topk()
        years = frame.loc[frame["bene_id"] == bene_id, "analytic_year"]
        if years.empty:
            raise HTTPException(status_code=404, detail=f"No summary found for {bene_id}.")
        analytic_year = int(years.max())

    bundle = load_cached_bundle(bene_id, analytic_year, settings=settings)
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence bundle found for {bene_id} ({analytic_year}).",
        )

    summary = generate_grounded_summary(
        bundle, settings=settings, allow_llm=not settings.study_mode
    )
    return summary


@router.post("/query/interpret")
def interpret_query(
    request: QueryInterpretRequest,
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> InterpretedQuery:
    _require_language_condition(study_ctx)
    interpreted = parse_natural_language_query(request.query)
    if study_ctx.study_mode and interpreted.action == "list_beneficiaries":
        year = study_analytic_year(get_settings())
        if year is not None and "analytic_year" not in interpreted.parameters:
            interpreted.parameters["analytic_year"] = year
            interpreted.confirmation_message = (
                f"{interpreted.confirmation_message} Data period: analytic year {year} "
                "(annual beneficiary aggregates)."
            )
    if study_ctx.study_mode and study_ctx.active_manipulations:
        interpreted = apply_query_manipulations(
            interpreted,
            active_manipulations=study_ctx.active_manipulations,
        )
    store_interpretation(interpreted, owner_id=study_ctx.participant_id)
    return public_interpretation(interpreted)


@router.post("/query/{query_id}/revise")
def revise_query(
    query_id: str,
    body: QueryCorrectionRequest,
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> InterpretedQuery:
    _require_language_condition(study_ctx)
    original = load_interpretation(query_id, owner_id=study_ctx.participant_id)
    if original is None:
        raise HTTPException(status_code=404, detail=f"Unknown query_id: {query_id}")
    if query_status(query_id, owner_id=study_ctx.participant_id) == "rejected":
        raise HTTPException(status_code=409, detail="This interpretation was cancelled.")
    try:
        revised = apply_correction(original, _correction_payload(body), query_id=str(uuid.uuid4()))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    store_interpretation(
        revised,
        owner_id=study_ctx.participant_id,
        parent_query_id=query_id,
        status="revised",
        lineage={"parent_query_id": query_id, "source": "participant_correction"},
    )
    return revised


@router.post("/query/{query_id}/reject")
def reject_query(
    query_id: str,
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> Dict[str, str]:
    _require_language_condition(study_ctx)
    if load_interpretation(query_id, owner_id=study_ctx.participant_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown query_id: {query_id}")
    set_query_status(query_id, "rejected", owner_id=study_ctx.participant_id)
    return {"query_id": query_id, "status": "rejected"}


def _public_result(result: QueryResult) -> QueryResult:
    result.parameters = public_parameters(dict(result.parameters))
    return result


@router.post("/query/execute")
def execute_query(
    request: QueryExecuteRequest,
    study_ctx: StudyRequestContext = Depends(get_study_context),
) -> QueryResult:
    if not request.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Query execution requires explicit user confirmation.",
        )
    if query_status(request.query_id, owner_id=study_ctx.participant_id) == "rejected":
        raise HTTPException(status_code=409, detail="This interpretation was cancelled.")

    cached = load_result(request.query_id, owner_id=study_ctx.participant_id)
    if cached is not None:
        return _public_result(cached)

    interpreted = load_interpretation(request.query_id, owner_id=study_ctx.participant_id)
    if interpreted is None:
        raise HTTPException(status_code=404, detail=f"Unknown query_id: {request.query_id}")

    result = execute_interpreted_query(interpreted)
    result.parameters = public_parameters(dict(interpreted.parameters))
    store_result(result, confirmed=True, owner_id=study_ctx.participant_id)
    set_query_status(request.query_id, "executed", owner_id=study_ctx.participant_id)
    return result
