from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from hc_analytics.language.grounding import EvidenceClaim
from hc_analytics.language.models import GroundedSummaryResponse, InterpretedQuery
from hc_analytics.study.loader import get_case_for_beneficiary
from hc_analytics.study.models import StudyCaseDefinition, StudyContextPayload


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _apply_misleading_risk(
    payload: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    column = str(config.get("risk_column", "hospitalization_risk"))
    delta = float(config.get("delta", -0.25))
    risk_scores = payload.get("risk_scores", {})
    if column in risk_scores and risk_scores[column] is not None:
        risk_scores[column] = round(_clamp01(float(risk_scores[column]) + delta), 6)
    rows = payload.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if column in row and row[column] is not None:
                row[column] = round(_clamp01(float(row[column]) + delta), 6)
    return payload


def _apply_low_confidence(
    payload: Dict[str, Any],
    config: Dict[str, Any],
    context: StudyContextPayload,
) -> Dict[str, Any]:
    columns = config.get("risk_columns", ["hospitalization_risk"])
    for column in columns:
        context.risk_confidence[str(column)] = "low"
    return payload


def apply_beneficiary_manipulations(
    payload: Dict[str, Any],
    *,
    case: Optional[StudyCaseDefinition],
    active_manipulations: List[str],
) -> Dict[str, Any]:
    if case is None or not active_manipulations:
        return payload

    mutated = copy.deepcopy(payload)
    context = StudyContextPayload(case_id=case.case_id)

    for manipulation_id in active_manipulations:
        config = case.manipulations.get(manipulation_id)
        if config is None:
            continue
        manipulation_type = config.get("type")
        if manipulation_type == "misleading_risk":
            mutated = _apply_misleading_risk(mutated, config)
            context.manipulation_applied.append(manipulation_id)
        elif manipulation_type == "low_confidence":
            mutated = _apply_low_confidence(mutated, config, context)
            context.manipulation_applied.append(manipulation_id)

    if context.manipulation_applied:
        mutated["study_context"] = context.model_dump()
    return mutated


def apply_beneficiary_list_manipulations(
    payload: Dict[str, Any],
    *,
    active_manipulations: List[str],
    participant_id: Optional[str],
    task_id: Optional[str],
    settings,
) -> Dict[str, Any]:
    if not active_manipulations:
        return payload

    rows = payload.get("rows")
    if not isinstance(rows, list):
        return payload

    mutated = copy.deepcopy(payload)
    for index, row in enumerate(mutated["rows"]):
        bene_id = row.get("bene_id")
        analytic_year = row.get("analytic_year")
        case = get_case_for_beneficiary(bene_id, analytic_year, settings=settings)
        if case is None:
            continue
        row_payload = apply_beneficiary_manipulations(
            {"risk_scores": row, "rows": [row]},
            case=case,
            active_manipulations=active_manipulations,
        )
        mutated["rows"][index] = row_payload["rows"][0]
    return mutated


def apply_explanation_manipulations(
    payload: Dict[str, Any],
    *,
    case: Optional[StudyCaseDefinition],
    active_manipulations: List[str],
) -> Dict[str, Any]:
    if case is None or not active_manipulations:
        return payload

    mutated = copy.deepcopy(payload)
    context = StudyContextPayload(case_id=case.case_id)
    contributors = mutated.get("contributors", [])
    stability = mutated.get("stability", [])

    for manipulation_id in active_manipulations:
        config = case.manipulations.get(manipulation_id)
        if config is None:
            continue
        if config.get("type") == "inverted_shap" and len(contributors) >= 2:
            target = config.get("target")
            scoped = [
                item
                for item in contributors
                if target is None or item.get("target") == target
            ]
            if len(scoped) >= 2:
                first_index = contributors.index(scoped[0])
                second_index = contributors.index(scoped[1])
                contributors[first_index], contributors[second_index] = (
                    contributors[second_index],
                    contributors[first_index],
                )
                context.manipulation_applied.append(manipulation_id)
        elif config.get("type") == "low_confidence":
            for item in stability:
                item["stability_badge"] = config.get("force_stability", "red")
                item["stability_score"] = 0.2
            for item in contributors:
                item["stability_badge"] = config.get("force_stability", "red")
                item["stability_score"] = 0.2
            context.manipulation_applied.append(manipulation_id)

    if context.manipulation_applied:
        mutated["contributors"] = contributors
        mutated["stability"] = stability
        mutated["study_context"] = context.model_dump()
    return mutated


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

    if context.manipulation_applied:
        payload = mutated.model_dump()
        payload["study_context"] = context.model_dump()
        return GroundedSummaryResponse.model_validate(payload)
    return mutated


def apply_query_manipulations(
    interpreted: InterpretedQuery,
    *,
    active_manipulations: List[str],
    case: Optional[StudyCaseDefinition] = None,
) -> InterpretedQuery:
    if "M4" not in active_manipulations:
        return interpreted

    mutated = interpreted.model_copy(deep=True)
    chronic_filter = mutated.parameters.get("chronic_filter")
    if chronic_filter == "has_diabetes":
        mutated.parameters["chronic_filter"] = "has_hypertension"
        mutated.parameters["chronic_value"] = 1
        mutated.confirmation_message = mutated.confirmation_message.replace(
            "diabetes",
            "hypertension",
        )
        mutated.confirmation_message = mutated.confirmation_message.replace(
            "has_diabetes",
            "has_hypertension",
        )
        payload = mutated.model_dump()
        payload["study_context"] = {
            "case_id": case.case_id if case else None,
            "active_manipulations": ["M4"],
            "manipulation_applied": ["M4"],
        }
        return InterpretedQuery.model_validate(payload)
    return interpreted
