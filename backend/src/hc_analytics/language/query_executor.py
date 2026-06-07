from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from hc_analytics.api.data_access import frame_to_records, load_cohort_summary_payload, load_merged_dashboard_frame
from hc_analytics.language.models import InterpretedQuery, QueryResult
from hc_analytics.language.summaries import cohort_query_narrative


def _apply_beneficiary_filters(frame: pd.DataFrame, parameters: Dict[str, Any]) -> pd.DataFrame:
    chronic_filter = parameters.get("chronic_filter")
    if chronic_filter and chronic_filter in frame.columns:
        chronic_value = parameters.get("chronic_value", 1)
        frame = frame.loc[frame[chronic_filter] == chronic_value]
    return frame


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

    frame = load_merged_dashboard_frame()
    frame = _apply_beneficiary_filters(frame, interpreted.parameters)

    sort_by = interpreted.parameters.get("sort_by", "hospitalization_risk")
    descending = bool(interpreted.parameters.get("descending", True))
    limit = int(interpreted.parameters.get("limit", 100))

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
        parameters=interpreted.parameters,
    )
    narrative = grounded.claims[0].statement if grounded.claims else None

    return QueryResult(
        query_id=interpreted.query_id,
        action=interpreted.action,
        natural_language=interpreted.natural_language,
        parameters=interpreted.parameters,
        row_count=len(records),
        rows=records,
        grounded_narrative=narrative,
        claims=grounded.claims,
    )
