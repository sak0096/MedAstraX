"""Canonical Study 2 cohort specification shared by baseline filters and NL query."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from hc_analytics.api.data_access import load_merged_dashboard_frame
from hc_analytics.config import Settings, get_settings
from hc_analytics.study.loader import get_study_catalog

# Matched S2-T1 / S2-T2 primary cohort task. The source data are annual
# beneficiary aggregates, so the study uses an explicit analytic year rather
# than claiming a rolling month window that cannot be represented faithfully.
PRIMARY_COHORT_SPEC: Dict[str, Any] = {
    "chronic_filter": "has_diabetes",
    "chronic_value": 1,
    "min_total_claims": 50,
    "sort_by": "hospitalization_risk",
    "descending": True,
    "limit": 25,
}


def study_analytic_year(settings: Optional[Settings] = None) -> Optional[int]:
    catalog = get_study_catalog(settings=settings or get_settings())
    if catalog is None:
        return None
    return int(catalog.default_analytic_year)


def cohort_spec_for_task(
    task_id: str,
    *,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    """Return the frozen canonical cohort definition for a scored study task."""
    year = study_analytic_year(settings)
    if task_id == "S1-T2":
        return {
            "chronic_filter": None,
            "chronic_value": None,
            "min_total_claims": None,
            "sort_by": "hospitalization_risk",
            "descending": True,
            "limit": 5,
            "analytic_year": year,
        }
    if task_id in {"S2-T1", "S2-T2"}:
        return {**PRIMARY_COHORT_SPEC, "analytic_year": year}
    if task_id == "S2-T6":
        return {
            "chronic_filter": "has_chf",
            "chronic_value": 1,
            "min_total_claims": 30,
            "sort_by": "elevated_cost_risk",
            "descending": True,
            "limit": 10,
            "analytic_year": year,
        }
    raise ValueError(f"No canonical cohort specification is defined for task {task_id}.")


def apply_cohort_filters(
    frame: pd.DataFrame,
    parameters: Dict[str, Any],
    *,
    default_analytic_year: Optional[int] = None,
) -> pd.DataFrame:
    """Apply the same cohort filters used by baseline chips and NL execution."""
    year = parameters.get("analytic_year", default_analytic_year)
    if year is not None and "analytic_year" in frame.columns:
        frame = frame.loc[frame["analytic_year"] == int(year)]

    chronic_filter = parameters.get("chronic_filter")
    if chronic_filter and chronic_filter in frame.columns:
        chronic_value = parameters.get("chronic_value", 1)
        frame = frame.loc[frame[chronic_filter] == chronic_value]

    min_total_claims = parameters.get("min_total_claims")
    if min_total_claims is not None and "total_claims" in frame.columns:
        frame = frame.loc[frame["total_claims"] >= int(min_total_claims)]
    return frame


def resolve_cohort_rows(
    parameters: Optional[Dict[str, Any]] = None,
    *,
    settings: Optional[Settings] = None,
) -> pd.DataFrame:
    runtime = settings or get_settings()
    params = {**PRIMARY_COHORT_SPEC, **(parameters or {})}
    year = study_analytic_year(runtime)
    frame = load_merged_dashboard_frame()
    frame = apply_cohort_filters(frame, params, default_analytic_year=year)
    sort_by = str(params.get("sort_by", "hospitalization_risk"))
    descending = bool(params.get("descending", True))
    limit = int(params.get("limit", 25))
    if sort_by in frame.columns:
        frame = frame.sort_values(sort_by, ascending=not descending)
    return frame.head(limit).copy()


def expected_cohort_ids(
    parameters: Optional[Dict[str, Any]] = None,
    *,
    settings: Optional[Settings] = None,
) -> List[str]:
    rows = resolve_cohort_rows(parameters, settings=settings)
    if "bene_id" not in rows.columns:
        return []
    return [str(value) for value in rows["bene_id"].tolist()]


def cohort_ground_truth(
    parameters: Optional[Dict[str, Any]] = None,
    *,
    settings: Optional[Settings] = None,
) -> Dict[str, Any]:
    params = {**PRIMARY_COHORT_SPEC, **(parameters or {})}
    ids = expected_cohort_ids(params, settings=settings)
    return {
        "expected_ids": ids,
        "expected_count": len(ids),
        "expected_top_bene_id": ids[0] if ids else None,
        "parameters": {
            "chronic_filter": params.get("chronic_filter"),
            "chronic_value": params.get("chronic_value"),
            "min_total_claims": params.get("min_total_claims"),
            "limit": params.get("limit"),
            "sort_by": params.get("sort_by"),
            "descending": params.get("descending"),
            "analytic_year": params.get("analytic_year", study_analytic_year(settings)),
        },
    }


def score_fields_from_responses(responses: Dict[str, Any]) -> Dict[str, Any]:
    result_ids: Sequence[str] = responses.get("result_ids") or responses.get("beneficiary_ids") or []
    top = responses.get("top_bene_id")
    if not top and result_ids:
        top = result_ids[0]
    count = responses.get("result_count")
    if count is None:
        count = len(list(result_ids)) if result_ids else None
    return {
        "result_ids": [str(item) for item in result_ids if str(item).strip()],
        "top_bene_id": str(top).strip() if top else None,
        "result_count": int(count) if count is not None else None,
    }
