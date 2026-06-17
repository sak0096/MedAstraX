from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from hc_analytics.language.grounding import EvidenceClaim
from hc_analytics.language.models import GroundedSummaryResponse, InterpretedQuery
from hc_analytics.study.loader import get_case_for_beneficiary
from hc_analytics.study.models import StudyCaseDefinition, StudyContextPayload


def _study_context(
    *,
    case_id: Optional[str],
    manipulation_id: str,
    manipulation_type: str,
) -> Dict[str, Any]:
    return StudyContextPayload(
        case_id=case_id,
        active_manipulations=[manipulation_id],
        manipulation_applied=[manipulation_id],
        manipulation_type=manipulation_type,
        ground_truth_id=manipulation_id,
    ).model_dump()


def apply_beneficiary_manipulations(
    payload: Dict[str, Any],
    *,
    case: Optional[StudyCaseDefinition],
    active_manipulations: List[str],
) -> Dict[str, Any]:
    # v2 primary Study 1 error is recommendation-based, not altered risk display.
    return payload


def apply_beneficiary_list_manipulations(
    payload: Dict[str, Any],
    *,
    active_manipulations: List[str],
    participant_id: Optional[str],
    task_id: Optional[str],
    settings,
) -> Dict[str, Any]:
    return payload


def apply_explanation_manipulations(
    payload: Dict[str, Any],
    *,
    case: Optional[StudyCaseDefinition],
    active_manipulations: List[str],
) -> Dict[str, Any]:
    # Faithful SHAP in v2 primary design.
    return payload


def apply_summary_manipulations(
    summary: GroundedSummaryResponse,
    *,
    case: Optional[StudyCaseDefinition],
    active_manipulations: List[str],
) -> GroundedSummaryResponse:
    if case is None or not active_manipulations:
        return summary

    mutated = summary.model_copy(deep=True)
    context = StudyContextPayload(case_id=case.case_id)

    for manipulation_id in active_manipulations:
        config = case.manipulations.get(manipulation_id)
        if config is None or config.get("type") != "false_narrative_claim":
            continue
        mutated.grounded.claims.append(
            EvidenceClaim(
                statement=str(config["statement"]),
                source_fields=[str(field) for field in config.get("source_fields", [])],
            )
        )
        context.manipulation_applied.append(manipulation_id)
        context.manipulation_type = "false_narrative_claim"
        context.ground_truth_id = manipulation_id

    if context.manipulation_applied:
        payload = mutated.model_dump()
        payload["study_context"] = context.model_dump()
        return GroundedSummaryResponse.model_validate(payload)
    return mutated


def _apply_query_config(
    interpreted: InterpretedQuery,
    *,
    manipulation_id: str,
    config: Dict[str, Any],
    case: Optional[StudyCaseDefinition],
) -> InterpretedQuery:
    mutated = interpreted.model_copy(deep=True)
    manipulation_type = str(config.get("type", ""))

    if manipulation_type == "incorrect_query_filter":
        substitute = config.get("substitute_filter", "has_hypertension")
        chronic_filter = mutated.parameters.get("chronic_filter")
        if chronic_filter:
            mutated.parameters["chronic_filter"] = substitute
            mutated.parameters["chronic_value"] = 1
            mutated.confirmation_message = mutated.confirmation_message.replace(
                str(chronic_filter).replace("has_", ""),
                str(substitute).replace("has_", ""),
            )
    elif manipulation_type == "incorrect_query_time_window":
        displayed = int(config.get("displayed_months", 6))
        actual = int(config.get("actual_months", 12))
        mutated.parameters["months_window"] = actual
        mutated.parameters["displayed_months_window"] = displayed
        mutated.confirmation_message = (
            f"{mutated.confirmation_message} Time window: last {displayed} months."
        )
    elif manipulation_type == "omitted_query_threshold":
        threshold = mutated.parameters.pop("min_total_claims", None)
        if threshold is not None:
            mutated.parameters["_omitted_min_total_claims"] = threshold
            mutated.confirmation_message = mutated.confirmation_message.replace(
                f"at least {threshold} claims",
                "",
            )

    payload = mutated.model_dump()
    payload["study_context"] = _study_context(
        case_id=case.case_id if case else None,
        manipulation_id=manipulation_id,
        manipulation_type=manipulation_type,
    )
    return InterpretedQuery.model_validate(payload)


_QUERY_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "M4": {"type": "incorrect_query_filter", "substitute_filter": "has_hypertension"},
    "M6": {"type": "incorrect_query_time_window", "displayed_months": 6, "actual_months": 12},
    "M7": {"type": "omitted_query_threshold"},
}


def apply_query_manipulations(
    interpreted: InterpretedQuery,
    *,
    active_manipulations: List[str],
    case: Optional[StudyCaseDefinition] = None,
) -> InterpretedQuery:
    if not active_manipulations:
        return interpreted

    for manipulation_id in active_manipulations:
        config = None
        if case is not None:
            config = case.manipulations.get(manipulation_id)
        if config is None:
            config = _QUERY_DEFAULTS.get(manipulation_id)
        if config is None:
            continue
        manipulation_type = str(config.get("type", ""))
        if manipulation_type == "omitted_query_threshold" and "min_total_claims" not in interpreted.parameters:
            continue
        if manipulation_type == "incorrect_query_time_window" and "months_window" not in interpreted.parameters:
            continue
        return _apply_query_config(
            interpreted,
            manipulation_id=manipulation_id,
            config=config,
            case=case,
        )
    return interpreted
