from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.language.models import InterpretedQuery
from hc_analytics.study.manipulations import apply_query_manipulations, apply_summary_manipulations
from hc_analytics.study.cohort_spec import cohort_spec_for_task
from hc_analytics.study.models import StudyCaseDefinition
from hc_analytics.study.priority import compute_priority_score, incorrect_recommendation_ranking, rank_case_ids
from hc_analytics.study.recommendations import build_outreach_recommendation
from hc_analytics.study.scoring import score_outreach_trial, score_session_events
from hc_analytics.study.session import assign_case_set, assign_manipulations


@pytest.fixture()
def study_settings(tmp_path: Path) -> Settings:
    repo = tmp_path / "repo"
    study_dir = repo / "study"
    study_dir.mkdir(parents=True)
    catalog = {
        "schema_version": "2.0",
        "default_analytic_year": 2022,
        "manipulation_catalog": {
            "M2": "incorrect recommendation",
            "M3": "false claim",
            "M4": "wrong filter",
            "M6": "wrong analytic year",
            "M7": "omitted threshold",
        },
        "priority_rule": {
            "description": "Test priority rule",
            "weights": {"inpatient_claims": 3.0},
        },
        "comprehension": {"pass_threshold": 1, "questions": []},
        "comprehension_study2": {
            "pass_threshold": 1,
            "questions": [
                {
                    "question_id": "S2Q1",
                    "prompt": "Study 2 question",
                    "choices": ["a", "b"],
                    "correct_index": 0,
                }
            ],
        },
        "case_sets": {"alpha": ["B-01", "B-02"], "beta": ["B-01b", "B-02b"]},
        "cases": [
            {
                "case_id": "B-01",
                "label": "Case B-01",
                "bene_id": "BENE-1",
                "analytic_year": 2022,
                "case_set": "alpha",
                "ground_truth": {
                    "inpatient_claims": 1,
                    "outpatient_claims": 2,
                    "chronic_condition_count": 0,
                    "total_claims": 10,
                    "priority_score": 8.0,
                },
                "manipulations": {"M2": {"type": "incorrect_outreach_recommendation"}},
            },
            {
                "case_id": "B-02",
                "label": "Case B-02",
                "bene_id": "BENE-2",
                "analytic_year": 2022,
                "case_set": "alpha",
                "ground_truth": {
                    "inpatient_claims": 5,
                    "outpatient_claims": 1,
                    "chronic_condition_count": 1,
                    "total_claims": 20,
                    "priority_score": 18.0,
                },
                "manipulations": {"M2": {"type": "incorrect_outreach_recommendation"}},
            },
            {
                "case_id": "B-01b",
                "label": "Case B-01b",
                "bene_id": "BENE-1b",
                "analytic_year": 2022,
                "case_set": "beta",
                "ground_truth": {
                    "inpatient_claims": 2,
                    "outpatient_claims": 1,
                    "chronic_condition_count": 0,
                    "total_claims": 8,
                    "priority_score": 7.8,
                },
                "manipulations": {"M2": {"type": "incorrect_outreach_recommendation"}},
            },
            {
                "case_id": "B-02b",
                "label": "Case B-02b",
                "bene_id": "BENE-2b",
                "analytic_year": 2022,
                "case_set": "beta",
                "ground_truth": {
                    "inpatient_claims": 6,
                    "outpatient_claims": 0,
                    "chronic_condition_count": 0,
                    "total_claims": 12,
                    "priority_score": 19.2,
                },
                "manipulations": {"M2": {"type": "incorrect_outreach_recommendation"}},
            },
            {
                "case_id": "B-07",
                "label": "Case B-07",
                "bene_id": "BENE-7",
                "analytic_year": 2022,
                "case_set": "shared",
                "ground_truth": {"hospitalization_risk": 0.8},
                "manipulations": {
                    "M3": {
                        "type": "false_narrative_claim",
                        "statement": "False diabetes claim",
                        "source_fields": ["has_diabetes"],
                    }
                },
            },
        ],
        "tasks": [
            {
                "task_id": "S1-T5",
                "study": "study1",
                "title": "Outreach",
                "time_limit_min": 8,
                "instructions": "Rank cases",
                "response_type": "sequential_ranking",
                "requires_cases": [],
                "manipulation_slot": "study1",
                "sequential_judgment": True,
            },
            {
                "task_id": "S2-T2",
                "study": "study2",
                "title": "Query",
                "time_limit_min": 5,
                "instructions": "Query",
                "response_type": "query_flow",
                "requires_cases": [],
                "manipulation_slot": "study2",
            },
        ],
        "task_sets": {"study1": ["S1-T5"], "study2": ["S2-T2"]},
    }
    (study_dir / "study_cases.json").write_text(json.dumps(catalog), encoding="utf-8")
    return Settings(
        repo_root=repo,
        study_mode=True,
        study_cases_path=Path("study/study_cases.json"),
        log_events=False,
    )


def test_assign_manipulations_v2_is_deterministic() -> None:
    first = assign_manipulations("P001")
    second = assign_manipulations("P001")
    assert first == second
    assert first["S1-T5"] in {"M2", "correct"}
    assert first["S2-T2"] in {"M4", "M6", "M7", "correct"}
    assert first["S2-T3"] in {"M3", "correct"}
    assert first["S2-T6"] in {"M4", "M6", "M7", "correct"}


def test_study2_error_density_near_proposal_range() -> None:
    slots = ("S2-T2", "S2-T3", "S2-T6")
    error_hits = 0
    total = 0
    for index in range(200):
        assigned = assign_manipulations(f"P{index:03d}")
        for slot in slots:
            total += 1
            if assigned[slot] != "correct":
                error_hits += 1
    rate = error_hits / total
    assert 0.15 <= rate <= 0.35


def test_study1_outreach_counterbalancing() -> None:
    outcomes = {assign_manipulations(f"P{i:03d}")["S1-T5"] for i in range(32)}
    assert "M2" in outcomes
    assert "correct" in outcomes


def test_study1_complementary_errors_across_conditions() -> None:
    from hc_analytics.study.session import study1_recommendation_is_manipulated

    for pid in ("P001", "P002", "P010"):
        baseline = study1_recommendation_is_manipulated(pid, "baseline")
        xai = study1_recommendation_is_manipulated(pid, "xai")
        assert baseline != xai


def test_study2_errors_are_per_task() -> None:
    assigned = assign_manipulations("P001")
    assert assigned["S2-T2"] != assigned["S2-T3"] or assigned["S2-T3"] == "correct"
    if assigned["S2-T6"] != "correct":
        assert assigned["S2-T6"] != assigned["S2-T2"]


def test_assign_case_set() -> None:
    assert assign_case_set("P001") in {"alpha", "beta"}
    first = assign_case_set("P001", condition="baseline", study="study1")
    second_condition = "xai"
    second = assign_case_set("P001", condition=second_condition, study="study1")
    assert first != second


def test_priority_ranking() -> None:
    records = {
        "B-01": {"inpatient_claims": 1, "outpatient_claims": 0, "chronic_condition_count": 0, "total_claims": 5},
        "B-02": {"inpatient_claims": 4, "outpatient_claims": 0, "chronic_condition_count": 0, "total_claims": 5},
    }
    assert rank_case_ids(["B-01", "B-02"], case_records=records) == ["B-02", "B-01"]
    assert compute_priority_score(records["B-02"]) == 12.5


def test_incorrect_recommendation_ranking() -> None:
    correct = ["B-02", "B-01"]
    manipulated = incorrect_recommendation_ranking(correct)
    assert manipulated[0] == "B-01"
    assert manipulated[-1] == "B-02"


def test_build_outreach_recommendation(study_settings: Settings) -> None:
    faithful = build_outreach_recommendation(["B-01", "B-02"], manipulated=False, settings=study_settings)
    assert faithful["correct_ranking"] == ["B-02", "B-01"]
    assert faithful["recommended_ranking"] == faithful["correct_ranking"]

    manipulated = build_outreach_recommendation(["B-01", "B-02"], manipulated=True, settings=study_settings)
    assert manipulated["recommended_ranking"][0] == "B-01"
    assert manipulated["manipulated"] is True


def test_query_filter_manipulation() -> None:
    interpreted = InterpretedQuery(
        query_id="q1",
        natural_language="top 25 with diabetes",
        action="list_beneficiaries",
        parameters={"chronic_filter": "has_diabetes", "chronic_value": 1, "limit": 25, "sort_by": "hospitalization_risk"},
        confirmation_message="with diabetes flagged",
    )
    mutated = apply_query_manipulations(interpreted, active_manipulations=["M4"])
    assert mutated.parameters["chronic_filter"] == "has_hypertension"


def test_query_analytic_year_manipulation_changes_execution_and_confirmation() -> None:
    interpreted = InterpretedQuery(
        query_id="q2",
        natural_language="top 10 in analytic year 2022",
        action="list_beneficiaries",
        parameters={"limit": 10, "sort_by": "hospitalization_risk", "analytic_year": 2022},
        confirmation_message="sorted list during analytic year 2022",
    )
    mutated = apply_query_manipulations(interpreted, active_manipulations=["M6"])
    assert mutated.parameters["analytic_year"] == 2021
    assert "analytic year 2021" in mutated.confirmation_message


def test_canonical_cohort_specs_are_frozen_by_task(study_settings: Settings) -> None:
    assert cohort_spec_for_task("S1-T2", settings=study_settings)["limit"] == 5
    assert cohort_spec_for_task("S1-T2", settings=study_settings)["chronic_filter"] is None
    assert cohort_spec_for_task("S2-T2", settings=study_settings)["chronic_filter"] == "has_diabetes"
    assert cohort_spec_for_task("S2-T6", settings=study_settings)["chronic_filter"] == "has_chf"
    assert cohort_spec_for_task("S2-T6", settings=study_settings)["analytic_year"] == 2022


def test_query_response_cannot_redefine_ground_truth(
    study_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("hc_analytics.config.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.loader.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.api.routes.study.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.context.get_settings", lambda: study_settings)
    captured: dict = {}

    def fake_ground_truth(parameters, *, settings):
        captured.update(parameters)
        return {"expected_ids": [], "expected_count": 0, "parameters": parameters}

    monkeypatch.setattr("hc_analytics.api.routes.study.cohort_ground_truth", fake_ground_truth)
    client = TestClient(app)
    response = client.post(
        "/api/study/tasks/S2-T2/response",
        json={
            "participant_id": "P001",
            "session_id": "session-12345678",
            "phase": "final",
            "responses": {
                "parameters": {
                    "chronic_filter": "has_hypertension",
                    "analytic_year": 2021,
                }
            },
        },
    )

    assert response.status_code == 200
    assert captured["chronic_filter"] == "has_diabetes"
    assert captured["analytic_year"] == 2022


def test_score_outreach_trial_harmful_switch() -> None:
    metrics = score_outreach_trial(
        initial_ranking=["B-02", "B-01"],
        final_ranking=["B-01", "B-02"],
        correct_ranking=["B-02", "B-01"],
        recommendation_ranking=["B-01", "B-02"],
        manipulated=True,
    )
    assert metrics["harmful_switching"] is True
    assert metrics["incorrect_ai_adherence"] is True


def test_score_outreach_trial_beneficial_correction() -> None:
    metrics = score_outreach_trial(
        initial_ranking=["B-01", "B-02"],
        final_ranking=["B-02", "B-01"],
        correct_ranking=["B-02", "B-01"],
        recommendation_ranking=["B-02", "B-01"],
        manipulated=False,
    )
    assert metrics["beneficial_correction"] is True
    assert metrics["harmful_switching"] is False
    assert metrics["top1_correct"] is True
    assert metrics["weight_of_advice"] == 1.0


def test_kendall_and_interpretation_scoring() -> None:
    from hc_analytics.study.scoring import kendall_tau_distance, score_claim_detection, score_interpretation, score_query_set

    assert kendall_tau_distance(["A", "B", "C"], ["A", "B", "C"]) == 0.0
    interpretation = score_interpretation(
        [{"feature": "inpatient_claims", "direction": "increases_risk"}],
        [
            {"feature": "inpatient_claims", "direction": "increases_risk"},
            {"feature": "age", "direction": "decreases_risk"},
        ],
    )
    assert interpretation["correct_count"] == 1
    assert interpretation["partial_credit"] == 0.5
    claim = score_claim_detection(
        supported="unsupported",
        flagged_claim="two inpatient admissions",
        manipulated=True,
        unsupported_statement="Beneficiary had two inpatient admissions in the analytic year.",
    )
    assert claim["detected_unsupported_claim"] is True
    wrong_sentence = score_claim_detection(
        supported="unsupported",
        flagged_claim="age is incorrect",
        manipulated=True,
        unsupported_statement="Beneficiary had two inpatient admissions in the analytic year.",
    )
    assert wrong_sentence["detected_unsupported_claim"] is False
    query = score_query_set(["2", "1"], ["1", "2", "3"])
    assert query["exact_match"] is False
    assert query["precision"] == 1.0
    assert query["recall"] == 0.6667
    set_match = score_query_set(["2", "1", "3"], ["1", "2", "3"])
    assert set_match["exact_match"] is True
    assert set_match["exact_ordered_match"] is False


def test_sparse_duplicate_events_do_not_erase_ground_truth() -> None:
    events = [
        {
            "event_type": "task_response",
            "timestamp": "2026-01-01T00:01:00",
            "task_id": "S1-T5",
            "payload": {
                "trial_id": "trial-dup",
                "phase": "final",
                "responses": {"ranking": ["B-02", "B-01"]},
                "manipulated": True,
                "ground_truth": {
                    "correct_ranking": ["B-02", "B-01"],
                    "recommendation_ranking": ["B-01", "B-02"],
                },
            },
        },
        {
            "event_type": "task_response",
            "timestamp": "2026-01-01T00:01:01",
            "task_id": "S1-T5",
            "payload": {"trial_id": "trial-dup", "phase": "final"},
        },
    ]
    report = score_session_events(events)
    assert report["trial_count"] == 1
    assert report["trials"][0]["final_correct"] is True


def test_study_session_hides_assignments_unless_facilitator(
    study_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("hc_analytics.config.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.loader.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.api.routes.study.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.session.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.context.get_settings", lambda: study_settings)
    client = TestClient(app)
    public = client.get("/api/study/session", params={"participant_id": "P001"})
    assert public.status_code == 200
    assert public.json()["assignments"] == {}
    facilitator = client.get(
        "/api/study/session",
        params={"participant_id": "P001", "facilitator": True},
    )
    assert facilitator.status_code == 200
    assert facilitator.json()["assignments"]["S1-T5"] in {"correct", "M2"}


def test_score_session_events_reads_initial_response_event() -> None:
    events = [
        {
            "event_type": "task_initial_response",
            "timestamp": "2026-01-01T00:00:00",
            "task_id": "S1-T5",
            "payload": {
                "trial_id": "trial-1",
                "phase": "initial",
                "responses": {"ranking": ["B-01", "B-02"]},
            },
        },
        {
            "event_type": "task_response",
            "timestamp": "2026-01-01T00:05:00",
            "task_id": "S1-T5",
            "payload": {
                "trial_id": "trial-1",
                "phase": "final",
                "responses": {"ranking": ["B-02", "B-01"]},
                "manipulated": False,
                "ground_truth": {
                    "correct_ranking": ["B-02", "B-01"],
                    "recommendation_ranking": ["B-02", "B-01"],
                },
            },
        },
    ]
    report = score_session_events(events)
    assert report["trial_count"] == 1
    assert report["faithful_trial_count"] == 1
    assert report["trials"][0]["beneficial_correction"] is True


def test_study_api_session_and_sequential_response(study_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("hc_analytics.config.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.loader.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.api.routes.study.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.session.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.context.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.recommendations.get_settings", lambda: study_settings)
    client = TestClient(app)

    session = client.get("/api/study/session", params={"participant_id": "P001"})
    assert session.status_code == 200
    body = session.json()
    assert body["study_mode_enabled"] is True
    assert body["case_set"] in {"alpha", "beta"}
    assert body["assignments"] == {}

    comprehension = client.post(
        "/api/study/comprehension",
        json={
            "participant_id": "P001",
            "session_id": "session-12345678",
            "study": "study2",
            "answers": {"S2Q1": 0},
        },
        headers={"X-Study-Arm": "study2"},
    )
    assert comprehension.status_code == 200
    assert comprehension.json()["passed"] is True
    assert comprehension.json()["study"] == "study2"

    started = client.post(
        "/api/study/tasks/S1-T5/start",
        params={"participant_id": "P001", "session_id": "session-12345678"},
    )
    assert started.status_code == 200
    payload = started.json()
    assert payload["task"]["task_id"] == "S1-T5"
    assert payload["trial_id"]

    recommendation = client.get(
        "/api/study/tasks/S1-T5/recommendation",
        params={"participant_id": "P001"},
    )
    assert recommendation.status_code == 200
    assert "recommended_ranking" in recommendation.json()

    initial = client.post(
        "/api/study/tasks/S1-T5/response",
        json={
            "participant_id": "P001",
            "session_id": "session-12345678",
            "trial_id": payload["trial_id"],
            "phase": "initial",
            "responses": {"ranking": ["B-02", "B-01"]},
            "confidence": 5,
        },
    )
    assert initial.status_code == 200

    final = client.post(
        "/api/study/tasks/S1-T5/response",
        json={
            "participant_id": "P001",
            "session_id": "session-12345678",
            "trial_id": payload["trial_id"],
            "phase": "final",
            "responses": {"ranking": ["B-02", "B-01"]},
            "confidence": 6,
            "reliance_source": "priority_rule",
        },
    )
    assert final.status_code == 200
