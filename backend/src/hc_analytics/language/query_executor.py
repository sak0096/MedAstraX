from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from hc_analytics.api.data_access import frame_to_records, load_cohort_summary_payload, load_merged_dashboard_frame
from hc_analytics.config import get_settings
from hc_analytics.language.models import InterpretedQuery, QueryResult
from hc_analytics.language.summaries import cohort_query_narrative
from hc_analytics.study.cohort_spec import apply_cohort_filters, study_analytic_year


def execute_interpreted_query(interpreted: InterpretedQuery, *, use_cache: bool = True) -> QueryResult:
    del use_cache  # cache lookup handled by route layer

    if interpreted.action == "cohort_summary":
        summary = load_cohort_summary_payload()
        narrative = (
            f"Cohort covers {summary['beneficiary_years']:,} beneficiary-years across "
            f"{summary['distinct_beneficiaries']:,} beneficiaries. "
            f"Average claims per year: {summary['avg_total_claims']:.1f}. "
            f"Next-year hospitalization rate: {summary['hospitalization_rate_next_year']:.1%}."
        )
        grounded = cohort_query_narrative(
            natural_language=interpreted.natural_language,
            row_count=int(summary["beneficiary_years"]),
            parameters={"sort_by": "cohort_summary"},
        )
        return QueryResult(
            query_id=interpreted.query_id,
            action=interpreted.action,
            natural_language=interpreted.natural_language,
            parameters=interpreted.parameters,
            row_count=int(summary["beneficiary_years"]),
            cohort_summary=summary,
            grounded_narrative=narrative,
            claims=grounded.claims,
        )

    settings = get_settings()
    default_year = study_analytic_year(settings) if settings.study_mode else None
    parameters = dict(interpreted.parameters)
    if default_year is not None and "analytic_year" not in parameters:
        parameters["analytic_year"] = default_year

    frame = load_merged_dashboard_frame()
    frame = apply_cohort_filters(frame, parameters, default_analytic_year=default_year)

    sort_by = parameters.get("sort_by", "hospitalization_risk")
    descending = bool(parameters.get("descending", True))
    limit = int(parameters.get("limit", 100))

    if sort_by in frame.columns:
        frame = frame.sort_values(sort_by, ascending=not descending)
    frame = frame.head(limit)

    list_columns = [
        "bene_id",
        "analytic_year",
        "age",
        "sex",
        "state_code",
        "total_claims",
        "total_payment_amt",
        "chronic_condition_count",
        "hospitalization_risk",
        "high_utilization_risk",
        "elevated_cost_risk",
    ]
    available = [column for column in list_columns if column in frame.columns]
    records = frame_to_records(frame[available])

    grounded = cohort_query_narrative(
        natural_language=interpreted.natural_language,
        row_count=len(records),
        parameters=parameters,
    )
    narrative = grounded.claims[0].statement if grounded.claims else None

    return QueryResult(
        query_id=interpreted.query_id,
        action=interpreted.action,
        natural_language=interpreted.natural_language,
        parameters=parameters,
        row_count=len(records),
        rows=records,
        grounded_narrative=narrative,
        claims=grounded.claims,
    )
