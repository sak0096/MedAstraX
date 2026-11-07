"""Security, enrollment, and query-correction behavior for the pilot foundation."""

from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.language.corrections import apply_correction
from hc_analytics.language.models import InterpretedQuery
from hc_analytics.language.openai_provider import polish_narrative_with_llm
from hc_analytics.persistence.repository import CapExceeded, StateConflict, StudyRepository
from hc_analytics.release import release_blockers
from hc_analytics.security.redaction import contains_protected_key
from hc_analytics.study.manipulations import apply_query_manipulations
from hc_analytics.study.scoring import score_designation_transition, score_session_events
from hc_analytics.study.session import assign_manipulations, validate_assignment_design


def _catalog(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schema_version": "2.0",
        "default_analytic_year": 2022,
        "manipulation_catalog": {"M2": "incorrect recommendation", "M4": "wrong filter"},
        "priority_rule": {"description": "Test rule", "weights": {"inpatient_claims": 3.0}},
        "comprehension": {"pass_threshold": 0, "questions": []},
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
        "case_sets": {"alpha": ["B-01", "B-02"], "beta": ["B-01", "B-02"]},
        "cases": [
            {
                "case_id": "B-01",
                "label": "Case B-01",
                "bene_id": "BENE-1",
                "analytic_year": 2022,
                "case_set": "alpha",
                "ground_truth": {
                    "inpatient_claims": 1,
                    "outpatient_claims": 0,
                    "chronic_condition_count": 0,
                    "total_claims": 5,
                    "priority_score": 3.5,
                },
                "manipulations": {},
            },
            {
                "case_id": "B-02",
                "label": "Case B-02",
                "bene_id": "BENE-2",
                "analytic_year": 2022,
                "case_set": "alpha",
                "ground_truth": {
                    "inpatient_claims": 4,
                    "outpatient_claims": 0,
                    "chronic_condition_count": 0,
                    "total_claims": 5,
                    "priority_score": 12.5,
                },
                "manipulations": {},
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
                "sequential_judgment": False,
            },
        ],
        "task_sets": {"study1": ["S1-T5"], "study2": ["S2-T2"]},
    }
    (path / "study_cases.json").write_text(json.dumps(catalog), encoding="utf-8")


def _settings(tmp_path: Path, **overrides) -> Settings:
    repo = tmp_path / "repo"
    (repo / "artifacts").mkdir(parents=True)
    _catalog(repo / "study")
    values = {
        "repo_root": repo,
        "artifacts_dir": Path("artifacts"),
        "study_mode": True,
        "study_cases_path": Path("study/study_cases.json"),
        "log_events": False,
        "environment": "local",
        "storage_backend": "sqlite",
        "enforce_progression": True,
        "integration_secret": "integration-test-secret",
        "admin_token": "admin-test-secret",
        "enrollment_cap_per_study": 2,
        "enrollment_cap_total": 3,
        "allow_synthetic_launch": True,
        "recruitment_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


def _patch(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    modules = [
        "hc_analytics.config",
        "hc_analytics.api.app",
        "hc_analytics.api.routes.study",
        "hc_analytics.api.routes.integration",
        "hc_analytics.api.routes.admin",
        "hc_analytics.api.routes.language",
        "hc_analytics.api.routes.instrumentation",
        "hc_analytics.api.routes.explanations",
        "hc_analytics.study.context",
        "hc_analytics.study.loader",
        "hc_analytics.study.session",
        "hc_analytics.study.recommendations",
        "hc_analytics.language.query_cache",
        "hc_analytics.persistence.repository",
        "hc_analytics.security.auth",
    ]
    for name in modules:
        module = __import__(name, fromlist=["get_settings"])
        if hasattr(module, "get_settings"):
            monkeypatch.setattr(module, "get_settings", lambda settings=settings: settings)


def _launch(
    client: TestClient, *, nonce: str, study: str = "study2", namespace: str = "test"
) -> dict:
    response = client.post(
        "/api/integration/launch",
        headers={"Authorization": "Bearer integration-test-secret"},
        json={
            "survey_id": "SV_TEST",
            "survey_version": "october-unverified",
            "stage": "consent",
            "consent_authorized": True,
            "study": study,
            "nonce": nonce,
            "namespace": namespace,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_launch_exchange_is_one_time_and_hides_the_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    _patch(monkeypatch, settings)
    client = TestClient(app)
    anonymous = client.post(
        "/api/integration/launch",
        json={
            "survey_id": "SV_TEST",
            "survey_version": "v",
            "stage": "consent",
            "consent_authorized": True,
            "study": "study2",
            "nonce": "nonce-unauth-01",
            "namespace": "test",
        },
    )
    assert anonymous.status_code == 401
    prolific = client.post(
        "/api/integration/launch",
        headers={"Authorization": "Bearer integration-test-secret"},
        json={
            "survey_id": "SV_TEST",
            "survey_version": "october-unverified",
            "stage": "consent",
            "consent_authorized": True,
            "study": "study2",
            "nonce": "nonce-prolific-01",
            "namespace": "test",
            "enrollment_reference": "0123456789abcdef01234567",
        },
    )
    assert prolific.status_code == 400
    pilot = client.post(
        "/api/integration/launch",
        headers={"Authorization": "Bearer integration-test-secret"},
        json={
            "survey_id": "SV_TEST",
            "survey_version": "october-unverified",
            "stage": "consent",
            "consent_authorized": True,
            "study": "study2",
            "nonce": "nonce-pilot-0001",
            "namespace": "pilot",
        },
    )
    assert pilot.status_code == 403

    issued = _launch(client, nonce="nonce-auth-0001")
    assert issued["participant_code"].startswith("TEST-")
    assert not issued["participant_code"].startswith("P")
    replay = client.post(
        "/api/integration/launch",
        headers={"Authorization": "Bearer integration-test-secret"},
        json={
            "survey_id": "SV_TEST",
            "survey_version": "october-unverified",
            "stage": "consent",
            "consent_authorized": True,
            "study": "study2",
            "nonce": "nonce-auth-0001",
            "namespace": "test",
        },
    )
    assert replay.status_code == 409

    scanned = client.get(
        "/api/integration/exchange", params={"launch_token": issued["launch_token"]}
    )
    assert scanned.status_code in {404, 405}

    exchange = client.post(
        "/api/integration/exchange", json={"launch_token": issued["launch_token"]}
    )
    assert exchange.status_code == 200
    assert "participant_code" not in exchange.json()
    assert "HttpOnly" in exchange.headers["set-cookie"]
    assert "launch_token" not in exchange.text
    again = client.post("/api/integration/exchange", json={"launch_token": issued["launch_token"]})
    assert again.status_code == 401


def test_strict_session_locks_answers_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    _patch(monkeypatch, settings)
    client = TestClient(app)
    issued = _launch(client, nonce="nonce-session-01", study="study2")
    exchange = client.post(
        "/api/integration/exchange", json={"launch_token": issued["launch_token"]}
    )
    assert exchange.status_code == 200
    headers = {"X-MedAstraX-Request": "1"}
    enrollment = StudyRepository.from_settings(settings).get_enrollment_by_code(
        issued["participant_code"]
    )
    meta = client.get(
        "/api/meta",
        headers={
            **headers,
            "X-Study-Condition": "xai",
            "X-Study-Arm": "study1",
        },
    )
    assert meta.status_code == 200
    assert meta.json()["experimental_condition"] == enrollment["condition_order"][0]
    assert meta.json()["assigned_study"] == "study2"
    public_session = client.get(
        "/api/study/session",
        headers=headers,
        params={"participant_id": issued["participant_code"], "facilitator": "1"},
    )
    assert public_session.status_code == 200
    assert "condition_order" not in public_session.json()
    assert "case_set_by_condition" not in public_session.json()
    assert "recommended_first_condition" not in public_session.json()
    assert all(
        "correct_index" not in question
        for question in public_session.json()["comprehension_study2"]["questions"]
    )

    blocked = client.post(
        "/api/study/tasks/S2-T2/start",
        headers=headers,
        params={"participant_id": issued["participant_code"]},
    )
    assert blocked.status_code == 409

    comprehension = client.post(
        "/api/study/comprehension",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "participant_id": issued["participant_code"],
            "session_id": "session-12345678",
            "study": "study1",
            "answers": {"S2Q1": 0},
            "idempotency_key": "attempt-key-1",
        },
    )
    assert comprehension.status_code == 200
    assert comprehension.json()["passed"] is True
    assert comprehension.json()["study"] == "study2"
    repeated = client.post(
        "/api/study/comprehension",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "participant_id": issued["participant_code"],
            "session_id": "session-12345678",
            "answers": {"S2Q1": 0},
            "idempotency_key": "attempt-key-1",
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["attempt_number"] == 1

    started = client.post(
        "/api/study/tasks/S1-T5/start",
        headers=headers,
        params={"participant_id": issued["participant_code"]},
    )
    assert started.status_code == 403

    query_task = client.post(
        "/api/study/tasks/S2-T2/start",
        headers=headers,
        params={"participant_id": issued["participant_code"]},
    )
    assert query_task.status_code == 200
    assert "active_manipulation" not in query_task.json()

    other = _launch(client, nonce="nonce-session-02", study="study1")
    other_exchange = client.post(
        "/api/integration/exchange", json={"launch_token": other["launch_token"]}
    )
    assert other_exchange.status_code == 200
    foreign = client.post(
        "/api/study/tasks/S1-T5/response",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "participant_id": other["participant_code"],
            "session_id": "session-12345678",
            "trial_id": query_task.json()["trial_id"],
            "phase": "initial",
            "responses": {"ranking": ["B-02", "B-01"]},
            "confidence": 40,
        },
    )
    assert foreign.status_code == 404


def test_initial_answer_is_immutable_and_assistance_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    _patch(monkeypatch, settings)
    client = TestClient(app)
    issued = _launch(client, nonce="nonce-lock-0001", study="study1")
    assert (
        client.post(
            "/api/integration/exchange", json={"launch_token": issued["launch_token"]}
        ).status_code
        == 200
    )
    headers = {"X-MedAstraX-Request": "1", "Content-Type": "application/json"}
    passed = client.post(
        "/api/study/comprehension",
        headers=headers,
        json={
            "participant_id": issued["participant_code"],
            "session_id": "session-12345678",
            "answers": {},
            "idempotency_key": "empty-pass",
        },
    )
    # Study 1 bank in this fixture has no questions, so the threshold is the question count (0).
    assert passed.status_code == 200
    assert passed.json()["passed"] is True
    started = client.post(
        "/api/study/tasks/S1-T5/start",
        headers={"X-MedAstraX-Request": "1"},
        params={"participant_id": issued["participant_code"]},
    )
    assert started.status_code == 200
    trial_id = started.json()["trial_id"]
    early = client.get(
        "/api/study/tasks/S1-T5/recommendation",
        headers={"X-MedAstraX-Request": "1"},
        params={"participant_id": issued["participant_code"], "trial_id": trial_id},
    )
    assert early.status_code == 409
    body = {
        "participant_id": issued["participant_code"],
        "session_id": "session-12345678",
        "trial_id": trial_id,
        "phase": "initial",
        "responses": {"ranking": ["B-02", "B-01"]},
        "confidence": 80,
    }
    first = client.post("/api/study/tasks/S1-T5/response", headers=headers, json=body)
    assert first.status_code == 200
    same = client.post("/api/study/tasks/S1-T5/response", headers=headers, json=body)
    assert same.status_code == 200
    assert same.json()["idempotent"] is True
    changed = dict(body)
    changed["responses"] = {"ranking": ["B-01", "B-02"]}
    conflict = client.post("/api/study/tasks/S1-T5/response", headers=headers, json=changed)
    assert conflict.status_code == 409
    recommendation = client.get(
        "/api/study/tasks/S1-T5/recommendation",
        headers={"X-MedAstraX-Request": "1"},
        params={"participant_id": issued["participant_code"], "trial_id": trial_id},
    )
    assert recommendation.status_code == 200
    assert contains_protected_key(recommendation.json()) is False
    invalid_final = client.post(
        "/api/study/tasks/S1-T5/response",
        headers=headers,
        json={**body, "phase": "final"},
    )
    assert invalid_final.status_code == 422
    valid_final = client.post(
        "/api/study/tasks/S1-T5/response",
        headers=headers,
        json={
            **body,
            "phase": "final",
            "responses": {
                "ranking": ["B-02", "B-01"],
                "decision_action": "keep",
                "decision_reason": "The visible rule supports the initial order.",
                "recommendation_support": 5,
            },
        },
    )
    assert valid_final.status_code == 200


def test_cap_race_and_deletion_does_not_free_the_slot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, enrollment_cap_per_study=2, enrollment_cap_total=2)
    _patch(monkeypatch, settings)
    repository = StudyRepository.from_settings(settings)

    def allocate(index: int):
        try:
            return repository.launch(
                namespace="test",
                study="study1",
                survey_id="SV_TEST",
                survey_version="v",
                nonce=f"race-nonce-{index}",
                enrollment_reference=None,
                environment="local",
                purpose="study_launch",
                ttl_seconds=60,
                cap_per_study=2,
                cap_total=2,
            )
        except CapExceeded:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(allocate, range(6)))
    issued = [item for item in results if item is not None]
    codes = [item["participant_code"] for item in issued]
    assert len(codes) == 2
    assert len(set(codes)) == 2
    assert all(code.startswith("TEST-") for code in codes)
    deleted_enrollment = next(
        item["enrollment_id"] for item in issued if item["participant_code"] == codes[0]
    )
    repository.store_query(
        query_id="delete-query",
        owner_id=deleted_enrollment,
        natural_language="synthetic query",
        interpreted_json="{}",
        parent_query_id=None,
        status="interpreted",
        lineage_json=None,
    )
    deleted = repository.delete_participant(codes[0])
    assert deleted["counts_toward_cap"] is True
    assert deleted["qualtrics_status"] == "pending"
    assert repository.load_query("delete-query", owner_id=deleted_enrollment) is None
    again = repository.delete_participant(codes[0])
    assert again["idempotent"] is True
    with pytest.raises(CapExceeded):
        repository.launch(
            namespace="test",
            study="study1",
            survey_id="SV_TEST",
            survey_version="v",
            nonce="race-nonce-extra",
            enrollment_reference=None,
            environment="local",
            purpose="study_launch",
            ttl_seconds=60,
            cap_per_study=2,
            cap_total=2,
        )
    repository.reapply_deletions()
    assert repository.get_enrollment_by_code(codes[0])["status"] == "deleted"


def test_admin_routes_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _patch(monkeypatch, settings)
    client = TestClient(app)
    issued = _launch(client, nonce="nonce-admin-0001")
    missing = client.get(f"/api/admin/enrollments/{issued['participant_code']}")
    assert missing.status_code == 401
    allowed = client.get(
        f"/api/admin/enrollments/{issued['participant_code']}",
        headers={"Authorization": "Bearer admin-test-secret"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["participant_code"] == issued["participant_code"]

    production = _settings(tmp_path / "prod", environment="production", storage_backend="sqlite")
    _patch(monkeypatch, production)
    closed = client.get(
        f"/api/admin/enrollments/{issued['participant_code']}",
        headers={"Authorization": "Bearer admin-test-secret"},
    )
    assert closed.status_code == 503
    ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["participant_launch_allowed"] is False


def test_production_admin_requires_entra_role(monkeypatch: pytest.MonkeyPatch) -> None:
    from hc_analytics.security import auth

    settings = Settings(
        environment="production",
        storage_backend="postgres",
        database_url="postgresql://not-used",
        session_secret="configured",
        integration_secret="configured",
        entra_tenant_id="tenant-id",
        entra_audience="api://medastrax",
        entra_admin_role="MedAstraX.ResearchAdmin",
    )
    with pytest.raises(HTTPException) as missing:
        auth.require_admin(None, settings)
    assert missing.value.status_code == 401

    monkeypatch.setattr(
        auth,
        "_decode_entra_token",
        lambda token, runtime: {"roles": ["Other.Role"]},
    )
    with pytest.raises(HTTPException) as forbidden:
        auth.require_admin("Bearer signed-token", settings)
    assert forbidden.value.status_code == 403

    monkeypatch.setattr(
        auth,
        "_decode_entra_token",
        lambda token, runtime: {"roles": ["MedAstraX.ResearchAdmin"]},
    )
    assert auth.require_admin("Bearer signed-token", settings) is None


def test_client_cannot_submit_critical_events_when_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, log_events=True)
    _patch(monkeypatch, settings)
    client = TestClient(app)
    response = client.post(
        "/api/instrumentation/events",
        json={
            "event_type": "task_start",
            "session_id": "session-api",
            "participant_id": "TEST-001",
            "payload": {"correct_ranking": ["B-02", "B-01"]},
        },
    )
    assert response.status_code == 403


def test_query_correction_does_not_reapply_the_manipulation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, enforce_progression=False, study_mode=False)
    _patch(monkeypatch, settings)
    interpreted = InterpretedQuery(
        query_id="q-year",
        natural_language="top 10 in analytic year 2022",
        action="list_beneficiaries",
        parameters={"limit": 10, "analytic_year": 2022, "sort_by": "hospitalization_risk"},
        confirmation_message="analytic year 2022",
    )
    manipulated = apply_query_manipulations(interpreted, active_manipulations=["M6"])
    assert manipulated.parameters["analytic_year"] == 2021
    corrected = apply_correction(manipulated, {"analytic_year": 2022}, query_id="q-corrected")
    assert corrected.parameters["analytic_year"] == 2022
    assert "_omitted_min_total_claims" not in corrected.parameters

    client = TestClient(app)
    created = client.post(
        "/api/language/query/interpret",
        json={"query": "top 10 with diabetes in analytic year 2022 with at least 50 claims"},
    )
    assert created.status_code == 200
    query_id = created.json()["query_id"]
    revised = client.post(
        f"/api/language/query/{query_id}/revise",
        json={"analytic_year": 2021, "min_total_claims": 30, "chronic_filter": "has_chf"},
    )
    assert revised.status_code == 200
    assert revised.json()["query_id"] != query_id
    assert revised.json()["parameters"]["analytic_year"] == 2021
    assert "_omitted_min_total_claims" not in revised.json()["parameters"]
    rejected = client.post(f"/api/language/query/{revised.json()['query_id']}/reject")
    assert rejected.status_code == 200
    executed = client.post(
        "/api/language/query/execute",
        json={"query_id": revised.json()["query_id"], "confirmed": True},
    )
    assert executed.status_code == 409


def test_live_generation_is_blocked_in_study_mode() -> None:
    settings = Settings(
        study_mode=True, llm_provider="openai", llm_api_key="test-key", llm_model="gpt-test"
    )
    with pytest.raises(RuntimeError, match="disabled during study sessions"):
        polish_narrative_with_llm(None, settings=settings)  # type: ignore[arg-type]


def test_designation_transition_requires_advice_consistency() -> None:
    metrics = score_designation_transition(
        initial="Supported",
        final="Not supported",
        displayed_designation="Not supported",
    )
    assert metrics["changed"] is True
    assert metrics["harmful_adoption"] is True
    assert metrics["advice_consistent_harmful_adoption"] is True
    assert metrics["harmful_adoption_status"] == "advice_consistent_transition"


def test_unknown_api_path_is_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _patch(monkeypatch, settings)
    client = TestClient(app)
    response = client.get("/api/not-a-route")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "html" not in response.text.lower()


def test_survey_callbacks_advance_two_server_owned_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path)
    _patch(monkeypatch, settings)
    from hc_analytics.api.routes import study as study_routes

    monkeypatch.setattr(study_routes, "cohort_ground_truth", lambda *args, **kwargs: {})
    client = TestClient(app)
    issued = _launch(client, nonce="callback-launch-01", study="study2")
    assert (
        client.post(
            "/api/integration/exchange", json={"launch_token": issued["launch_token"]}
        ).status_code
        == 200
    )
    headers = {"X-MedAstraX-Request": "1"}
    passed = client.post(
        "/api/study/comprehension",
        headers=headers,
        json={
            "participant_id": issued["participant_code"],
            "session_id": "callback-session",
            "answers": {"S2Q1": 0},
            "idempotency_key": "callback-attempt-1",
        },
    )
    assert passed.status_code == 200

    def complete_task() -> str:
        started = client.post(
            "/api/study/tasks/S2-T2/start",
            headers=headers,
            params={"participant_id": issued["participant_code"]},
        )
        assert started.status_code == 200, started.text
        response = client.post(
            "/api/study/tasks/S2-T2/response",
            headers=headers,
            json={
                "participant_id": issued["participant_code"],
                "session_id": "callback-session",
                "trial_id": started.json()["trial_id"],
                "phase": "single",
                "responses": {"result_count": 0, "top_bene_id": None},
                "confidence": 50,
            },
        )
        assert response.status_code == 200, response.text
        return started.json()["trial_id"]

    first_trial = complete_task()
    enrollment = StudyRepository.from_settings(settings).get_enrollment_by_code(
        issued["participant_code"]
    )
    assert enrollment["stage"] == "post_condition_1_survey"
    blocked = client.post(
        "/api/study/tasks/S2-T2/start",
        headers=headers,
        params={"participant_id": issued["participant_code"]},
    )
    assert blocked.status_code == 409

    callback = {
        "participant_code": issued["participant_code"],
        "survey_id": "SV_TEST",
        "survey_version": "october-unverified",
        "callback_type": "post_condition_1_complete",
        "nonce": "callback-stage-0001",
    }
    assert client.post("/api/integration/survey-callback", json=callback).status_code == 401
    advanced = client.post(
        "/api/integration/survey-callback",
        headers={"Authorization": "Bearer integration-test-secret"},
        json=callback,
    )
    assert advanced.status_code == 200
    assert advanced.json()["stage"] == "block2_tasks"
    replay = client.post(
        "/api/integration/survey-callback",
        headers={"Authorization": "Bearer integration-test-secret"},
        json=callback,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent"] is True

    second_trial = complete_task()
    assert second_trial != first_trial
    assert (
        StudyRepository.from_settings(settings).get_enrollment_by_code(issued["participant_code"])[
            "stage"
        ]
        == "final_survey"
    )
    final = client.post(
        "/api/integration/survey-callback",
        headers={"Authorization": "Bearer integration-test-secret"},
        json={
            **callback,
            "callback_type": "final_complete",
            "nonce": "callback-stage-0002",
            "retention_choice": "retain",
        },
    )
    assert final.status_code == 200
    assert final.json()["stage"] == "complete"
    assert client.get("/api/study/session", headers=headers).status_code == 401


def test_query_versions_are_owner_bound(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    repository = StudyRepository.from_settings(settings)
    repository.store_query(
        query_id="owner-query",
        owner_id="enrollment-a",
        natural_language="test query",
        interpreted_json="{}",
        parent_query_id=None,
        status="interpreted",
        lineage_json=None,
    )
    assert repository.load_query("owner-query", owner_id="enrollment-a") is not None
    assert repository.load_query("owner-query", owner_id="enrollment-b") is None
    with pytest.raises(StateConflict, match="Unknown query version"):
        repository.set_query_status("owner-query", owner_id="enrollment-b", status="rejected")


def test_supported_schema_upgrade_adds_block_index(tmp_path: Path) -> None:
    path = tmp_path / "version-two.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_meta (id INTEGER PRIMARY KEY, version TEXT NOT NULL);
        INSERT INTO schema_meta (id, version) VALUES (1, '2026-11-06.2');
        CREATE TABLE task_trials (
            trial_id TEXT PRIMARY KEY,
            enrollment_id TEXT NOT NULL,
            session_hash TEXT NOT NULL,
            task_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    connection.close()
    repository = StudyRepository("sqlite", str(path))
    repository.migrate()
    connection = sqlite3.connect(path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(task_trials)").fetchall()}
    enrollment_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(enrollments)").fetchall()
    }
    version = connection.execute("SELECT version FROM schema_meta WHERE id = 1").fetchone()[0]
    connection.close()
    assert "block_index" in columns
    assert {"is_pilot", "recruitment_stage", "confirmatory_eligible"} <= enrollment_columns
    assert version == "2026-11-06.4"


def test_release_manifest_detects_hash_mismatch(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "release").mkdir(parents=True)
    (repo / "study").mkdir()
    (repo / "study" / "asset.json").write_text("{}", encoding="utf-8")
    manifest = {
        "schema": "medastrax-release-v1",
        "code_commit": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "configuration_version": "v1",
        "schema_version": "v1",
        "assignment_version": "v1",
        "survey_version": "v1",
        "scoring_version": "v1",
        "human_adjudication_status": "complete",
        "participant_release_approved": True,
        "approvals": [
            {"role": role, "status": "approved", "evidence_ref": f"TEST-{role}"}
            for role in [
                "pi_release",
                "reviewed_source_comparison",
                "human_adjudication",
                "survey_branch_validation",
                "azure_security_operations",
            ]
        ],
        "assets": [{"path": "study/asset.json", "sha256": "0" * 64}],
    }
    (repo / "release" / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(
        repo_root=repo,
        release_manifest_path=Path("release/release-manifest.json"),
    )
    assert release_blockers(settings) == ["Release asset hash mismatch: study/asset.json"]


def test_october_task_catalog_contains_only_approved_tasks() -> None:
    catalog = json.loads(
        (Path(__file__).parents[2] / "study" / "study_cases.json").read_text(encoding="utf-8")
    )
    assert catalog["schema_version"] == "3.0-october-working-counterpart"
    assert catalog["task_sets"] == {
        "study1": ["S1-T0", "S1-T2", "S1-T3", "S1-T5"],
        "study2": ["S2-T0", "S2-T1", "S2-T3", "S2-T6"],
    }
    assert [item["prompt"] for item in catalog["comprehension"]["questions"]] == [
        "Which input has the largest weight in the outreach-priority rule?",
        (
            "If two members have the same inpatient and outpatient counts, "
            "what should you examine next?"
        ),
        "Before accepting an automated recommendation, what should you do?",
    ]


def test_blocked_assignment_validates_existing_case_and_error_map() -> None:
    repo = Path(__file__).parents[2]
    settings = Settings(repo_root=repo, study_mode=True)
    report = validate_assignment_design(per_study=60, settings=settings)
    for study in ("study1", "study2"):
        design = report["studies"][study]
        assert sorted(design["condition_order_counts"].values()) == [30, 30]
        assert design["case_set_first_counts"] == {"alpha": 30, "beta": 30}
        assert design["four_cell_counts"] == [15, 15, 15, 15]
    assert report["fixed_case_mapping"] == {"S1-T3": "B-07", "S2-T3": "B-15"}


def test_initial_pilot_is_labeled_capped_and_resume_reuses_enrollment(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        enrollment_cap_per_study=60,
        enrollment_cap_total=120,
        pilot_cap_per_study=3,
    )
    repository = StudyRepository.from_settings(settings)
    issued = []
    for index in range(3):
        record = repository.launch(
            namespace="pilot",
            study="study1",
            survey_id="SV_PILOT",
            survey_version="reviewed-working-counterpart",
            nonce=f"pilot-stage-nonce-{index}",
            enrollment_reference=f"opaque-resume-{index}",
            environment="local",
            purpose="study_launch",
            ttl_seconds=60,
            cap_per_study=60,
            cap_total=120,
            pilot_cap_per_study=3,
        )
        issued.append(record)
        stored = repository.get_enrollment_by_code(record["participant_code"])
        assert stored["is_pilot"] is True
        assert stored["recruitment_stage"] == "initial_pilot"
        assert stored["confirmatory_eligible"] is False
        assert stored["error_slots"] == assign_manipulations(record["participant_code"])

    plans = [repository.get_enrollment_by_code(item["participant_code"]) for item in issued]
    assert [item["condition_order"] for item in plans] == [
        ["baseline", "xai"],
        ["xai", "baseline"],
        ["baseline", "xai"],
    ]
    assert [item["case_sets"]["first"] for item in plans] == ["alpha", "alpha", "beta"]

    first_session = repository.consume_launch_token(
        issued[0]["launch_token"],
        environment="local",
        purpose="study_launch",
        session_ttl_seconds=300,
    )
    repository.set_stage(issued[0]["enrollment_id"], "block2_tasks")
    repository.append_event(
        event_type="task_start",
        enrollment_id=issued[0]["enrollment_id"],
        session_hash=first_session["session_hash"],
        task_id="S1-T2",
        payload={},
    )
    resumed = repository.launch(
        namespace="pilot",
        study="study1",
        survey_id="SV_PILOT",
        survey_version="reviewed-working-counterpart",
        nonce="pilot-stage-resume-nonce",
        enrollment_reference="opaque-resume-0",
        environment="local",
        purpose="study_launch",
        ttl_seconds=60,
        cap_per_study=60,
        cap_total=120,
        pilot_cap_per_study=3,
    )
    assert resumed["resumed"] is True
    assert resumed["enrollment_id"] == issued[0]["enrollment_id"]
    resumed_session = repository.consume_launch_token(
        resumed["launch_token"],
        environment="local",
        purpose="study_launch",
        session_ttl_seconds=300,
    )
    assert resumed_session["stage"] == "block2_tasks"
    assert resumed_session["block_index"] == 1
    assert resumed_session["condition"] == plans[0]["condition_order"][1]
    repository.append_event(
        event_type="task_response",
        enrollment_id=issued[0]["enrollment_id"],
        session_hash=resumed_session["session_hash"],
        task_id="S1-T2",
        payload={},
    )
    assert len(repository.load_session_events(resumed_session["session_hash"])) == 2
    with pytest.raises(CapExceeded):
        repository.launch(
            namespace="pilot",
            study="study1",
            survey_id="SV_PILOT",
            survey_version="reviewed-working-counterpart",
            nonce="pilot-stage-over-cap",
            enrollment_reference="opaque-resume-new",
            environment="local",
            purpose="study_launch",
            ttl_seconds=60,
            cap_per_study=60,
            cap_total=120,
            pilot_cap_per_study=3,
        )


def test_scoring_separates_harmful_metrics_and_preserves_raw_query_timing() -> None:
    events = [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "event_type": "task_initial_response",
            "task_id": "S1-T5",
            "payload": {
                "trial_id": "switch-only",
                "responses": {"ranking": ["A", "B", "C"]},
                "phase": "initial",
            },
        },
        {
            "timestamp": "2026-01-01T00:00:01Z",
            "event_type": "task_response",
            "task_id": "S1-T5",
            "payload": {
                "trial_id": "switch-only",
                "responses": {"ranking": ["A", "C", "B"]},
                "phase": "final",
                "manipulated": True,
                "ground_truth": {
                    "correct_ranking": ["A", "B", "C"],
                    "recommendation_ranking": ["B", "A", "C"],
                },
                "total_task_time_ms": 9000,
            },
        },
        {
            "timestamp": "2026-01-01T00:00:02Z",
            "event_type": "task_initial_response",
            "task_id": "S1-T5",
            "payload": {
                "trial_id": "adoption",
                "responses": {"ranking": ["A", "B", "C"]},
                "phase": "initial",
            },
        },
        {
            "timestamp": "2026-01-01T00:00:03Z",
            "event_type": "task_response",
            "task_id": "S1-T5",
            "payload": {
                "trial_id": "adoption",
                "responses": {"ranking": ["B", "A", "C"]},
                "phase": "final",
                "manipulated": True,
                "ground_truth": {
                    "correct_ranking": ["A", "B", "C"],
                    "recommendation_ranking": ["B", "A", "C"],
                },
            },
        },
        {
            "timestamp": "2026-01-01T00:00:04Z",
            "event_type": "query_submit",
            "payload": {"interpretation_time_ms": 125},
        },
        {
            "timestamp": "2026-01-01T00:00:05Z",
            "event_type": "query_revise",
            "payload": {"revision_time_ms": 240},
        },
        {
            "timestamp": "2026-01-01T00:00:06Z",
            "event_type": "query_confirm",
            "payload": {"execution_time_ms": 80},
        },
    ]
    report = score_session_events(events)
    assert report["harmful_switching_count"] == 2
    assert report["harmful_switching_opportunities"] == 2
    assert report["advice_consistent_harmful_adoption_count"] == 1
    assert report["advice_consistent_harmful_adoption_opportunities"] == 2
    assert report["raw_query_timing_ms"] == {
        "total_task": [9000.0],
        "interpretation": [125.0],
        "revision": [240.0],
        "execution": [80.0],
    }
