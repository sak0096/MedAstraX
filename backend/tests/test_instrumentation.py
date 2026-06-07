from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hc_analytics.api.app import app
from hc_analytics.config import Settings
from hc_analytics.instrumentation.events import EventType, StudyEvent, log_event
from hc_analytics.instrumentation.export import build_session_export, pseudonymize
from hc_analytics.instrumentation.store import list_sessions, load_session_events


@pytest.fixture()
def instrumentation_settings(tmp_path: Path) -> Settings:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    return Settings(
        repo_root=tmp_path,
        artifacts_dir=Path("artifacts"),
        log_events=True,
        study_id="pilot-test",
    )


def _patch_settings(monkeypatch, settings: Settings) -> None:
    monkeypatch.setattr("hc_analytics.api.app.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.api.routes.instrumentation.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.instrumentation.events.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.instrumentation.store.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.instrumentation.export.get_settings", lambda: settings)
    monkeypatch.setattr("hc_analytics.instrumentation.context.get_settings", lambda: settings)


def test_log_event_persists_jsonl_and_sqlite(
    instrumentation_settings: Settings,
    monkeypatch,
) -> None:
    _patch_settings(monkeypatch, instrumentation_settings)
    event = StudyEvent(
        event_type=EventType.SESSION_START,
        session_id="session-abc",
        participant_id="participant-001",
        payload={"task_id": "T1"},
    )
    record = log_event(event)
    assert record["event_type"] == "session_start"
    assert "version_context" in record

    sessions = list_sessions(settings=instrumentation_settings)
    assert len(sessions) == 1
    assert sessions[0]["event_count"] == 1

    loaded = load_session_events("session-abc", settings=instrumentation_settings)
    assert len(loaded) == 1
    assert loaded[0]["payload"]["task_id"] == "T1"


def test_export_pseudonymizes_identifiers(instrumentation_settings: Settings, monkeypatch) -> None:
    _patch_settings(monkeypatch, instrumentation_settings)
    log_event(
        StudyEvent(
            event_type=EventType.DRILL_DOWN,
            session_id="session-export",
            participant_id="participant-001",
            payload={"bene_id": "BENE-SECRET"},
        )
    )
    bundle = build_session_export("session-export", settings=instrumentation_settings)
    assert bundle["event_count"] == 1
    event = bundle["events"][0]
    assert "participant_id" not in event
    assert event["participant_pseudonym"] == pseudonymize("participant-001", "pilot-test")
    assert event["payload"]["bene_id_pseudonym"] == pseudonymize("BENE-SECRET", "pilot-test")
    assert "BENE-SECRET" not in str(bundle)


def test_instrumentation_api_records_and_exports(
    instrumentation_settings: Settings,
    monkeypatch,
) -> None:
    _patch_settings(monkeypatch, instrumentation_settings)
    client = TestClient(app)

    meta = client.get("/api/instrumentation/meta")
    assert meta.status_code == 200
    assert meta.json()["instrumentation_enabled"] is True

    response = client.post(
        "/api/instrumentation/events",
        json={
            "event_type": "filter_change",
            "session_id": "session-api",
            "participant_id": "P9",
            "payload": {"sort_by": "hospitalization_risk"},
        },
    )
    assert response.status_code == 200
    assert response.json()["stored"] is True

    export = client.post(
        "/api/instrumentation/export",
        json={"session_id": "session-api"},
    )
    assert export.status_code == 200
    assert export.json()["event_count"] == 1

    app_meta = client.get("/api/meta")
    assert app_meta.status_code == 200
    assert app_meta.json()["prototype_phase"] == "8"


def test_log_event_noop_when_disabled(instrumentation_settings: Settings, monkeypatch) -> None:
    instrumentation_settings.log_events = False
    _patch_settings(monkeypatch, instrumentation_settings)
    record = log_event(
        StudyEvent(event_type=EventType.EXPORT, session_id="session-off", participant_id="P1")
    )
    assert record["event_type"] == "export"
    assert list_sessions(settings=instrumentation_settings) == []
