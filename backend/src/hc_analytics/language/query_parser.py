from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Optional

from hc_analytics.language.constants import DEFAULT_QUERY_LIMIT
from hc_analytics.language.models import InterpretedQuery, QueryAction

_LIMIT_RE = re.compile(r"\b(?:top|first|show)\s+(\d{1,3})\b", re.IGNORECASE)
_MONTHS_RE = re.compile(r"\blast\s+(\d{1,2})\s+months?\b", re.IGNORECASE)
_MIN_CLAIMS_RE = re.compile(
    r"\b(?:at least|minimum of|min(?:imum)?)\s+(\d{1,4})\s+claims?\b",
    re.IGNORECASE,
)
_CHRONIC_FILTERS = {
    "diabetes": "has_diabetes",
    "heart failure": "has_chf",
    "chf": "has_chf",
    "copd": "has_copd",
    "kidney": "has_ckd",
    "ckd": "has_ckd",
    "hypertension": "has_hypertension",
}


def _extract_limit(text: str) -> int:
    match = _LIMIT_RE.search(text)
    if match:
        return max(1, min(int(match.group(1)), 1000))
    if "top" in text or "highest" in text:
        return 25
    return DEFAULT_QUERY_LIMIT


def _detect_sort(text: str) -> str:
    lowered = text.lower()
    if "hospital" in lowered:
        return "hospitalization_risk"
    if "utilization" in lowered or "utilizer" in lowered or "claims" in lowered:
        return "total_claims"
    if "cost" in lowered or "payment" in lowered or "spend" in lowered:
        return "elevated_cost_risk"
    if "age" in lowered:
        return "age"
    return "hospitalization_risk"


def _extract_months_window(text: str) -> int:
    match = _MONTHS_RE.search(text)
    if match:
        return max(1, min(int(match.group(1)), 36))
    if "last year" in text.lower():
        return 12
    return 12


def _extract_min_total_claims(text: str) -> Optional[int]:
    match = _MIN_CLAIMS_RE.search(text)
    if match:
        return max(1, int(match.group(1)))
    return None


def _detect_chronic_filter(text: str) -> Optional[str]:
    lowered = text.lower()
    for phrase, field in _CHRONIC_FILTERS.items():
        if phrase in lowered:
            return field
    return None


def _is_cohort_query(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("cohort", "population", "overview", "summary", "average", "prevalence")
    )


def parse_natural_language_query(query: str) -> InterpretedQuery:
    text = query.strip()
    lowered = text.lower()
    query_id = str(uuid.uuid4())

    if _is_cohort_query(text):
        return InterpretedQuery(
            query_id=query_id,
            natural_language=text,
            action="cohort_summary",
            parameters={},
            confirmation_message=(
                "Load cohort-level summary metrics (beneficiary counts, utilization, chronic prevalence)."
            ),
        )

    parameters: Dict[str, Any] = {
        "limit": _extract_limit(text),
        "sort_by": _detect_sort(text),
        "descending": "lowest" not in lowered and "ascending" not in lowered,
        "months_window": _extract_months_window(text),
    }
    chronic_filter = _detect_chronic_filter(text)
    if chronic_filter:
        parameters["chronic_filter"] = chronic_filter
        parameters["chronic_value"] = 1
    min_claims = _extract_min_total_claims(text)
    if min_claims is not None:
        parameters["min_total_claims"] = min_claims

    direction = "highest" if parameters["descending"] else "lowest"
    filter_text = ""
    if chronic_filter:
        filter_text = f" with {chronic_filter.replace('has_', '').replace('_', ' ')} flagged"
    threshold_text = ""
    if min_claims is not None:
        threshold_text = f" with at least {min_claims} claims"
    window_text = f" in the last {parameters['months_window']} months"

    confirmation = (
        f"Return up to {parameters['limit']} beneficiaries{filter_text}{threshold_text}{window_text}, "
        f"sorted by {parameters['sort_by']} ({direction} first)."
    )

    return InterpretedQuery(
        query_id=query_id,
        natural_language=text,
        action="list_beneficiaries",
        parameters=parameters,
        confirmation_message=confirmation,
    )
