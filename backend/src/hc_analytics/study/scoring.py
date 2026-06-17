"""Behavioral reliance scoring for exported study sessions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


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
        "followed_ai_recommendation": followed_ai,
        "harmful_switching": initial_correct and not final_correct and manipulated,
        "beneficial_correction": not initial_correct and final_correct and not manipulated,
        "appropriate_rejection": manipulated and not followed_ai and final_correct,
        "incorrect_ai_adherence": manipulated and followed_ai,
        "correct_ai_adherence": (not manipulated) and followed_ai,
        "underreliance": (not initial_correct) and (not final_correct) and not manipulated,
    }
    return metrics


def score_session_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    trials: Dict[str, Dict[str, Any]] = {}
    for event in sorted(events, key=lambda item: item.get("timestamp", "")):
        payload = event.get("payload") or {}
        trial_id = payload.get("trial_id") or event.get("task_id")
        if trial_id is None:
            continue
        bucket = trials.setdefault(str(trial_id), {"events": []})
        bucket["events"].append(event)
        event_type = event.get("event_type")
        if event_type not in {"task_response", "task_initial_response"}:
            continue
        phase = payload.get("phase")
        if event_type == "task_initial_response" or phase == "initial":
            bucket["initial_ranking"] = _normalize_ranking(
                (payload.get("responses") or {}).get("ranking")
            )
            bucket["initial_confidence"] = payload.get("confidence")
        elif phase == "final":
            bucket["final_ranking"] = _normalize_ranking(
                (payload.get("responses") or {}).get("ranking")
            )
            bucket["final_confidence"] = payload.get("confidence")
            bucket["ground_truth"] = payload.get("ground_truth")
            bucket["manipulated"] = payload.get("manipulated")

    scored: List[Dict[str, Any]] = []
    for trial_id, trial in trials.items():
        ground_truth = trial.get("ground_truth") or {}
        correct = _normalize_ranking(ground_truth.get("correct_ranking"))
        recommendation = _normalize_ranking(ground_truth.get("recommendation_ranking"))
        initial = trial.get("initial_ranking", [])
        final = trial.get("final_ranking", [])
        if not final or not correct:
            continue
        metrics = score_outreach_trial(
            initial_ranking=initial,
            final_ranking=final,
            correct_ranking=correct,
            recommendation_ranking=recommendation,
            manipulated=bool(trial.get("manipulated")),
        )
        scored.append({"trial_id": trial_id, "manipulated": bool(trial.get("manipulated")), **metrics})

    return {
        "trial_count": len(scored),
        "trials": scored,
        "harmful_switching_rate": _rate(scored, "harmful_switching"),
        "appropriate_rejection_rate": _rate(scored, "appropriate_rejection"),
        "beneficial_correction_rate": _rate(scored, "beneficial_correction"),
        "incorrect_trial_count": sum(1 for row in scored if row.get("manipulated")),
        "faithful_trial_count": sum(1 for row in scored if row.get("manipulated") is False),
        "harmful_switching_rate_incorrect_trials": _rate(
            [row for row in scored if row.get("manipulated")],
            "harmful_switching",
        ),
        "beneficial_correction_rate_faithful_trials": _rate(
            [row for row in scored if not row.get("manipulated")],
            "beneficial_correction",
        ),
    }


def _rate(rows: List[Dict[str, Any]], field: str) -> Optional[float]:
    if not rows:
        return None
    hits = sum(1 for row in rows if row.get(field))
    return round(hits / len(rows), 4)
