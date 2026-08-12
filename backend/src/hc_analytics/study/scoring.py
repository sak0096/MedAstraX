"""Behavioral reliance scoring for exported study sessions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


def _normalize_ranking(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def ranking_matches(left: Sequence[str], right: Sequence[str]) -> bool:
    return list(left) == list(right)


def follows_recommendation(final_ranking: Sequence[str], recommendation: Sequence[str]) -> bool:
    return ranking_matches(final_ranking, recommendation)


def top1_correct(ranking: Sequence[str], correct: Sequence[str]) -> bool:
    return bool(ranking) and bool(correct) and ranking[0] == correct[0]


def kendall_tau_distance(left: Sequence[str], right: Sequence[str]) -> Optional[float]:
    if not left or not right or set(left) != set(right):
        return None
    index = {item: position for position, item in enumerate(right)}
    ordered = [index[item] for item in left]
    inversions = 0
    pairs = 0
    for i, first in enumerate(ordered):
        for second in ordered[i + 1 :]:
            pairs += 1
            if first > second:
                inversions += 1
    if pairs == 0:
        return 0.0
    return round(inversions / pairs, 4)


def weight_of_advice(
    initial: Sequence[str],
    final: Sequence[str],
    advice: Sequence[str],
) -> Optional[float]:
    if not initial or not final or not advice:
        return None
    if set(initial) != set(final) or set(initial) != set(advice):
        return None
    init_pos = {item: index for index, item in enumerate(initial)}
    final_pos = {item: index for index, item in enumerate(final)}
    advice_pos = {item: index for index, item in enumerate(advice)}
    ratios = []
    for item in initial:
        delta_advice = advice_pos[item] - init_pos[item]
        delta_final = final_pos[item] - init_pos[item]
        if delta_advice == 0:
            continue
        ratios.append(delta_final / delta_advice)
    if not ratios:
        return None
    return round(sum(ratios) / len(ratios), 4)


def score_outreach_trial(
    *,
    initial_ranking: Sequence[str],
    final_ranking: Sequence[str],
    correct_ranking: Sequence[str],
    recommendation_ranking: Sequence[str],
    manipulated: bool,
) -> Dict[str, Any]:
    initial_correct = ranking_matches(initial_ranking, correct_ranking)
    final_correct = ranking_matches(final_ranking, correct_ranking)
    followed_ai = follows_recommendation(final_ranking, recommendation_ranking)

    metrics: Dict[str, Any] = {
        "initial_correct": initial_correct,
        "final_correct": final_correct,
        "top1_correct": top1_correct(final_ranking, correct_ranking),
        "kendall_tau_distance": kendall_tau_distance(final_ranking, correct_ranking),
        "weight_of_advice": weight_of_advice(initial_ranking, final_ranking, recommendation_ranking),
        "followed_ai_recommendation": followed_ai,
        "harmful_switching": initial_correct and not final_correct and manipulated,
        "beneficial_correction": not initial_correct and final_correct and not manipulated,
        "appropriate_rejection": manipulated and not followed_ai and final_correct,
        "incorrect_ai_adherence": manipulated and followed_ai,
        "correct_ai_adherence": (not manipulated) and followed_ai,
        "underreliance": (not initial_correct) and (not final_correct) and not manipulated,
    }
    return metrics


def score_interpretation(
    selected: Sequence[Dict[str, Any]],
    expected: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    expected_pairs: Set[Tuple[str, str]] = {
        (str(item.get("feature", "")), str(item.get("direction", "")))
        for item in expected
        if item.get("feature")
    }
    selected_pairs: Set[Tuple[str, str]] = {
        (str(item.get("feature", "")), str(item.get("direction", "")))
        for item in selected
        if item.get("feature")
    }
    matches = expected_pairs & selected_pairs
    total = max(len(expected_pairs), 1)
    return {
        "correct_count": len(matches),
        "expected_count": len(expected_pairs),
        "partial_credit": round(len(matches) / total, 4),
        "exact": selected_pairs == expected_pairs and bool(expected_pairs),
    }


def _claim_matches(flagged_claim: str, unsupported_statement: str) -> bool:
    flagged = flagged_claim.strip().lower()
    statement = unsupported_statement.strip().lower()
    if not flagged or not statement:
        return False
    if statement in flagged or flagged in statement:
        return True
    needle = statement[:40]
    return bool(needle) and needle in flagged


def score_claim_detection(
    *,
    supported: Optional[str],
    flagged_claim: Optional[str],
    manipulated: bool,
    unsupported_statement: Optional[str] = None,
) -> Dict[str, Any]:
    flagged = bool(flagged_claim and str(flagged_claim).strip())
    judged_unsupported = supported == "unsupported"
    detected = False
    if manipulated and judged_unsupported:
        if unsupported_statement:
            detected = flagged and _claim_matches(str(flagged_claim), unsupported_statement)
        else:
            detected = judged_unsupported
    return {
        "judged_unsupported": judged_unsupported,
        "flagged": flagged,
        "detected_unsupported_claim": detected,
        "false_alarm": (not manipulated) and judged_unsupported,
        "missed_unsupported_claim": manipulated and not detected,
    }


def score_query_set(
    result_ids: Sequence[str],
    expected_ids: Sequence[str],
    *,
    result_count: Optional[int] = None,
    top_bene_id: Optional[str] = None,
    expected_count: Optional[int] = None,
    expected_top_bene_id: Optional[str] = None,
) -> Dict[str, Any]:
    predicted = [str(item) for item in result_ids if str(item).strip()]
    expected = [str(item) for item in expected_ids if str(item).strip()]
    predicted_set = set(predicted)
    expected_set = set(expected)
    true_positive = len(predicted_set & expected_set)
    precision = round(true_positive / len(predicted_set), 4) if predicted_set else None
    recall = round(true_positive / len(expected_set), 4) if expected_set else None
    count = result_count if result_count is not None else len(predicted)
    expected_n = expected_count if expected_count is not None else len(expected)
    top = str(top_bene_id).strip() if top_bene_id else (predicted[0] if predicted else None)
    expected_top = (
        str(expected_top_bene_id).strip()
        if expected_top_bene_id
        else (expected[0] if expected else None)
    )
    return {
        "exact_match": predicted_set == expected_set and bool(expected_set),
        "exact_ordered_match": predicted == expected and bool(expected),
        "precision": precision,
        "recall": recall,
        "result_count": count,
        "expected_count": expected_n,
        "count_correct": count == expected_n if expected_n is not None else None,
        "top_bene_correct": bool(top and expected_top and top == expected_top),
    }


def _merge_non_null(bucket: Dict[str, Any], updates: Dict[str, Any]) -> None:
    for key, value in updates.items():
        if value is None:
            continue
        if value == [] and bucket.get(key):
            continue
        if value == {} and bucket.get(key):
            continue
        bucket[key] = value


def score_session_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    trials: Dict[str, Dict[str, Any]] = {}
    evidence_opens = 0
    evidence_dwell_ms: List[float] = []
    query_revises = 0
    query_rejects = 0
    for event in sorted(events, key=lambda item: item.get("timestamp", "")):
        payload = event.get("payload") or {}
        event_type = event.get("event_type")
        if event_type == "evidence_link_open":
            evidence_opens += 1
        if event_type == "evidence_dwell":
            duration = payload.get("duration_ms")
            if duration is not None:
                evidence_dwell_ms.append(float(duration))
        if event_type == "query_revise":
            query_revises += 1
        if event_type == "query_reject":
            query_rejects += 1
        trial_id = payload.get("trial_id") or event.get("task_id")
        if trial_id is None:
            continue
        bucket = trials.setdefault(str(trial_id), {"events": [], "task_id": event.get("task_id")})
        bucket["events"].append(event)
        if event_type not in {"task_response", "task_initial_response"}:
            continue
        # Sparse client duplicates (task_id/trial_id/phase only) must not erase rich server events.
        responses = payload.get("responses")
        if responses is None and payload.get("ground_truth") is None and payload.get("confidence") is None:
            continue
        responses = responses or {}
        phase = payload.get("phase")
        if event_type == "task_initial_response" or phase == "initial":
            _merge_non_null(
                bucket,
                {
                    "initial_ranking": _normalize_ranking(responses.get("ranking")),
                    "initial_confidence": payload.get("confidence"),
                    "initial_supported": responses.get("supported"),
                },
            )
        elif phase in {"final", "single", None} or event_type == "task_response":
            _merge_non_null(
                bucket,
                {
                    "final_ranking": _normalize_ranking(responses.get("ranking")),
                    "final_confidence": payload.get("confidence"),
                    "ground_truth": payload.get("ground_truth"),
                    "manipulated": payload.get("manipulated"),
                    "drivers": responses.get("drivers"),
                    "supported": responses.get("supported"),
                    "flagged_claim": responses.get("flagged_claim"),
                    "result_ids": responses.get("result_ids") or responses.get("beneficiary_ids"),
                    "result_count": responses.get("result_count"),
                    "top_bene_id": responses.get("top_bene_id"),
                    "time_ms": payload.get("time_ms"),
                    "timed_out": payload.get("timed_out"),
                },
            )

    outreach: List[Dict[str, Any]] = []
    interpretations: List[Dict[str, Any]] = []
    claims: List[Dict[str, Any]] = []
    queries: List[Dict[str, Any]] = []
    for trial_id, trial in trials.items():
        ground_truth = trial.get("ground_truth") or {}
        correct = _normalize_ranking(ground_truth.get("correct_ranking"))
        recommendation = _normalize_ranking(ground_truth.get("recommendation_ranking"))
        initial = trial.get("initial_ranking", [])
        final = trial.get("final_ranking", [])
        if final and correct:
            metrics = score_outreach_trial(
                initial_ranking=initial,
                final_ranking=final,
                correct_ranking=correct,
                recommendation_ranking=recommendation,
                manipulated=bool(trial.get("manipulated")),
            )
            outreach.append({"trial_id": trial_id, "manipulated": bool(trial.get("manipulated")), **metrics})
        expected_drivers = ground_truth.get("expected_drivers") or []
        if trial.get("drivers") and expected_drivers:
            interpretations.append(
                {
                    "trial_id": trial_id,
                    **score_interpretation(trial.get("drivers") or [], expected_drivers),
                }
            )
        if trial.get("supported") is not None or trial.get("flagged_claim"):
            claims.append(
                {
                    "trial_id": trial_id,
                    **score_claim_detection(
                        supported=trial.get("supported"),
                        flagged_claim=trial.get("flagged_claim"),
                        manipulated=bool(trial.get("manipulated")),
                        unsupported_statement=ground_truth.get("unsupported_statement"),
                    ),
                }
            )
        expected_ids = ground_truth.get("expected_ids") or []
        if trial.get("result_ids") is not None or trial.get("result_count") is not None or trial.get("top_bene_id"):
            query_metrics = score_query_set(
                trial.get("result_ids") or [],
                expected_ids,
                result_count=trial.get("result_count"),
                top_bene_id=trial.get("top_bene_id"),
                expected_count=ground_truth.get("expected_count"),
                expected_top_bene_id=ground_truth.get("expected_top_bene_id"),
            )
            queries.append({"trial_id": trial_id, **query_metrics})

    harmful_eligible = [row for row in outreach if row.get("manipulated") and row.get("initial_correct")]
    beneficial_eligible = [
        row for row in outreach if (not row.get("manipulated")) and (not row.get("initial_correct"))
    ]
    faithful = [row for row in outreach if not row.get("manipulated")]
    incorrect = [row for row in outreach if row.get("manipulated")]
    correct_adherence = _rate(faithful, "correct_ai_adherence")
    incorrect_adherence = _rate(incorrect, "incorrect_ai_adherence")
    appropriate_reliance_index = None
    if correct_adherence is not None and incorrect_adherence is not None:
        appropriate_reliance_index = round(correct_adherence - incorrect_adherence, 4)

    return {
        "trial_count": len(outreach),
        "trials": outreach,
        "interpretation_trials": interpretations,
        "claim_trials": claims,
        "query_trials": queries,
        "harmful_switching_rate": _rate(harmful_eligible, "harmful_switching"),
        "appropriate_rejection_rate": _rate(incorrect, "appropriate_rejection"),
        "beneficial_correction_rate": _rate(beneficial_eligible, "beneficial_correction"),
        "incorrect_trial_count": len(incorrect),
        "faithful_trial_count": len(faithful),
        "harmful_switching_rate_incorrect_trials": _rate(incorrect, "harmful_switching"),
        "beneficial_correction_rate_faithful_trials": _rate(faithful, "beneficial_correction"),
        "appropriate_reliance_index": appropriate_reliance_index,
        "mean_weight_of_advice": _mean([row.get("weight_of_advice") for row in outreach]),
        "mean_kendall_tau_distance": _mean([row.get("kendall_tau_distance") for row in outreach]),
        "claim_detection_rate": _rate(claims, "detected_unsupported_claim"),
        "query_exact_match_rate": _rate(queries, "exact_match"),
        "query_count_correct_rate": _rate(queries, "count_correct"),
        "query_top_bene_correct_rate": _rate(queries, "top_bene_correct"),
        "evidence_link_opens": evidence_opens,
        "mean_evidence_dwell_ms": _mean(evidence_dwell_ms),
        "query_revise_count": query_revises,
        "query_reject_count": query_rejects,
    }


def _rate(rows: List[Dict[str, Any]], field: str) -> Optional[float]:
    if not rows:
        return None
    hits = sum(1 for row in rows if row.get(field))
    return round(hits / len(rows), 4)


def _mean(values: List[Any]) -> Optional[float]:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), 4)
