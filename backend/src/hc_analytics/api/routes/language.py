from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from hc_analytics.config import get_settings
from hc_analytics.explainability.pipeline import load_cached_bundle
from hc_analytics.language.constants import LANGUAGE_SCHEMA_VERSION, SUPPORTED_QUERY_ACTIONS
from hc_analytics.language.models import (
    GroundedSummaryResponse,
    InterpretedQuery,
    QueryExecuteRequest,
    QueryInterpretRequest,
    QueryResult,
)
from hc_analytics.language.provider import active_provider_name, generate_grounded_summary, provider_configured
from hc_analytics.language.query_cache import (
    load_interpretation,
    load_result,
    store_interpretation,
    store_result,
)
from hc_analytics.language.query_executor import execute_interpreted_query
from hc_analytics.language.query_parser import parse_natural_language_query

router = APIRouter(prefix="/api/language", tags=["language"])


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
) -> GroundedSummaryResponse:
    settings = get_settings()
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
    return generate_grounded_summary(bundle, settings=settings)


@router.post("/query/interpret")
def interpret_query(request: QueryInterpretRequest) -> InterpretedQuery:
    interpreted = parse_natural_language_query(request.query)
    store_interpretation(interpreted)
    return interpreted


@router.post("/query/execute")
def execute_query(request: QueryExecuteRequest) -> QueryResult:
    if not request.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Query execution requires explicit user confirmation.",
        )

    cached = load_result(request.query_id)
    if cached is not None:
        return cached

    interpreted = load_interpretation(request.query_id)
    if interpreted is None:
        raise HTTPException(status_code=404, detail=f"Unknown query_id: {request.query_id}")

    result = execute_interpreted_query(interpreted)
    store_result(result, confirmed=True)
    return result
