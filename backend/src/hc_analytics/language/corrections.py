"""Participant corrections for a displayed query interpretation.

Re-parsing the original sentence under the same manipulation can recreate the
error. A correction therefore edits the displayed parameters directly and keeps
the prior version as its parent.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from hc_analytics.language.models import InterpretedQuery

ALLOWED_CHRONIC_FILTERS = {
    "has_diabetes",
    "has_chf",
    "has_copd",
    "has_ckd",
    "has_hypertension",
}

# Proposed card wording. It restates the interpreted fields only.
# The PI still needs to confirm this presentation against the reviewed exhibits.


def public_parameters(parameters: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in parameters.items() if not str(key).startswith("_")}


def describe_parameters(parameters: Dict[str, Any]) -> str:
    visible = public_parameters(parameters)
    parts = []
    chronic = visible.get("chronic_filter")
    if chronic:
        parts.append(f"condition filter {chronic}")
    if visible.get("analytic_year") is not None:
        parts.append(f"analytic year {visible['analytic_year']}")
    if visible.get("min_total_claims") is not None:
        parts.append(f"at least {visible['min_total_claims']} claims")
    if visible.get("limit") is not None:
        parts.append(f"limit {visible['limit']}")
    if not parts:
        return "Interpreted request: no filters were identified."
    return "Interpreted request: " + ", ".join(parts) + "."


def public_interpretation(interpreted: InterpretedQuery) -> InterpretedQuery:
    return interpreted.model_copy(
        update={"parameters": public_parameters(dict(interpreted.parameters))}
    )


def apply_correction(
    interpreted: InterpretedQuery,
    corrections: Dict[str, Optional[Any]],
    *,
    query_id: str,
) -> InterpretedQuery:
    if not corrections:
        raise ValueError("A correction needs at least one field.")
    parameters = public_parameters(dict(interpreted.parameters))
    for key, value in corrections.items():
        if key not in {"analytic_year", "chronic_filter", "min_total_claims"}:
            raise ValueError(f"Unsupported correction field: {key}")
        if key == "analytic_year":
            year = int(value)
            if year < 2000 or year > 2100:
                raise ValueError("Analytic year is out of range.")
            parameters["analytic_year"] = year
        elif key == "min_total_claims":
            if value is None:
                parameters.pop("min_total_claims", None)
            else:
                threshold = int(value)
                if threshold < 0 or threshold > 10000:
                    raise ValueError("Claims threshold is out of range.")
                parameters["min_total_claims"] = threshold
        elif key == "chronic_filter":
            if value is None:
                parameters.pop("chronic_filter", None)
                parameters.pop("chronic_value", None)
            else:
                if value not in ALLOWED_CHRONIC_FILTERS:
                    raise ValueError("Condition filter is not supported.")
                parameters["chronic_filter"] = value
                parameters["chronic_value"] = 1
    return InterpretedQuery(
        query_id=query_id,
        natural_language=interpreted.natural_language,
        action=interpreted.action,
        parameters=parameters,
        confirmation_message=describe_parameters(parameters),
        requires_confirmation=True,
    )
