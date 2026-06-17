from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.language.models import InterpretedQuery
from hc_analytics.study.manipulations import apply_query_manipulations, apply_summary_manipulations
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
            "M6": "wrong window",
            "M7": "omitted threshold",
        },
        "priority_rule": {
            "description": "Test priority rule",
            "weights": {"inpatient_claims": 3.0},
        },
        "comprehension": {"pass_threshold": 1, "questions": []},
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
    assert first["study1"] in {"M2", "correct"}
    assert first["study2"] in {"M3", "M4", "M6", "M7"}


def test_study1_outreach_counterbalancing() -> None:
    outcomes = {assign_manipulations(f"P{i:03d}")["study1"] for i in range(32)}
    assert "M2" in outcomes
    assert "correct" in outcomes


def test_assign_case_set() -> None:
    assert assign_case_set("P001") in {"alpha", "beta"}


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


def test_query_time_window_manipulation() -> None:
    interpreted = InterpretedQuery(
        query_id="q2",
        natural_language="top 10 in last 12 months",
        action="list_beneficiaries",
        parameters={"limit": 10, "sort_by": "hospitalization_risk", "months_window": 12},
        confirmation_message="sorted list",
    )
    mutated = apply_query_manipulations(interpreted, active_manipulations=["M6"])
    assert mutated.parameters["displayed_months_window"] == 6
    assert "6 months" in mutated.confirmation_message


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
    monkeypatch.setattr("hc_analytics.study.recommendations.get_settings", lambda: study_settings)
    client = TestClient(app)

    session = client.get("/api/study/session", params={"participant_id": "P001"})
    assert session.status_code == 200
    body = session.json()
    assert body["study_mode_enabled"] is True
    assert body["case_set"] in {"alpha", "beta"}

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
