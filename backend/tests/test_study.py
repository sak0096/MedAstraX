from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.study.manipulations import (
    apply_beneficiary_manipulations,
    apply_explanation_manipulations,
    apply_query_manipulations,
    apply_summary_manipulations,
)
from hc_analytics.study.models import StudyCaseDefinition
from hc_analytics.study.session import assign_manipulations


@pytest.fixture()
def study_settings(tmp_path: Path) -> Settings:
    repo = tmp_path / "repo"
    study_dir = repo / "study"
    study_dir.mkdir(parents=True)
    catalog = {
        "schema_version": "1.0",
        "default_analytic_year": 2022,
        "manipulation_catalog": {"M1": "invert", "M2": "risk", "M3": "claim", "M4": "query", "M5": "confidence"},
        "cases": [
            {
                "case_id": "B-07",
                "label": "Case B-07",
                "bene_id": "BENE-7",
                "analytic_year": 2022,
                "ground_truth": {"hospitalization_risk": 0.8},
                "manipulations": {
                    "M1": {"type": "inverted_shap", "target": "next_year_hospitalization"},
                    "M2": {"type": "misleading_risk", "risk_column": "hospitalization_risk", "delta": -0.25},
                    "M3": {
                        "type": "false_narrative_claim",
                        "statement": "False diabetes claim",
                        "source_fields": ["has_diabetes"],
                    },
                    "M5": {"type": "low_confidence", "risk_columns": ["hospitalization_risk"], "force_stability": "red"},
                },
            }
        ],
        "tasks": [
            {
                "task_id": "S1-T3",
                "study": "study1",
                "title": "Risk drivers",
                "time_limit_min": 6,
                "instructions": "Open B-07",
                "response_type": "feature_list",
                "requires_cases": ["B-07"],
                "manipulation_slot": "study1",
                "conditions": [],
            }
        ],
        "task_sets": {"study1": ["S1-T3"], "study2": []},
    }
    (study_dir / "study_cases.json").write_text(json.dumps(catalog), encoding="utf-8")
    return Settings(
        repo_root=repo,
        study_mode=True,
        study_cases_path=Path("study/study_cases.json"),
        log_events=False,
    )


def test_assign_manipulations_is_deterministic() -> None:
    first = assign_manipulations("P001")
    second = assign_manipulations("P001")
    assert first == second
    assert first["study1"] in {"M1", "M2", "M5"}
    assert first["study2"] in {"M2", "M3", "M4"}


def test_misleading_risk_manipulation(study_settings: Settings) -> None:
    from hc_analytics.study.loader import get_case_by_id

    loaded = get_case_by_id("B-07", settings=study_settings)
    payload = {"risk_scores": {"hospitalization_risk": 0.8}}
    mutated = apply_beneficiary_manipulations(payload, case=loaded, active_manipulations=["M2"])
    assert mutated["risk_scores"]["hospitalization_risk"] == 0.55
    assert mutated["study_context"]["manipulation_applied"] == ["M2"]


def test_inverted_shap_manipulation(study_settings: Settings) -> None:
    from hc_analytics.study.loader import get_case_by_id

    loaded = get_case_by_id("B-07", settings=study_settings)
    payload = {
        "contributors": [
            {"feature": "a", "shap_value": 0.3, "direction": "increases_risk", "target": "next_year_hospitalization"},
            {"feature": "b", "shap_value": 0.2, "direction": "increases_risk", "target": "next_year_hospitalization"},
        ],
        "stability": [],
    }
    mutated = apply_explanation_manipulations(payload, case=loaded, active_manipulations=["M1"])
    assert mutated["contributors"][0]["feature"] == "b"
    assert mutated["contributors"][1]["feature"] == "a"


def test_query_filter_manipulation() -> None:
    from hc_analytics.language.models import InterpretedQuery

    interpreted = InterpretedQuery(
        query_id="q1",
        natural_language="top 25 with diabetes",
        action="list_beneficiaries",
        parameters={"chronic_filter": "has_diabetes", "chronic_value": 1, "limit": 25, "sort_by": "hospitalization_risk"},
        confirmation_message="with diabetes flagged",
    )
    mutated = apply_query_manipulations(interpreted, active_manipulations=["M4"])
    assert mutated.parameters["chronic_filter"] == "has_hypertension"


def test_study_api_session_and_task_start(study_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("hc_analytics.config.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.loader.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.api.routes.study.get_settings", lambda: study_settings)
    monkeypatch.setattr("hc_analytics.study.session.get_settings", lambda: study_settings)
    client = TestClient(app)

    session = client.get("/api/study/session", params={"participant_id": "P001"})
    assert session.status_code == 200
    body = session.json()
    assert body["study_mode_enabled"] is True
    assert "study1" in body["assignments"]

    started = client.post(
        "/api/study/tasks/S1-T3/start",
        params={"participant_id": "P001", "session_id": "session-12345678"},
    )
    assert started.status_code == 200
    assert started.json()["task"]["task_id"] == "S1-T3"

    response = client.post(
        "/api/study/tasks/S1-T3/response",
        json={
            "participant_id": "P001",
            "session_id": "session-12345678",
            "responses": {"text": "feature a"},
            "time_ms": 1200,
        },
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "S1-T3"
