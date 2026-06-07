from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.instrumentation.context import build_version_context
from hc_analytics.instrumentation.events import StudyEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS study_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    session_id TEXT,
    participant_id TEXT,
    study_id TEXT,
    timestamp TEXT NOT NULL,
    event_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_study_events_session ON study_events(session_id);
"""


def _logs_dir(settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    path = settings.artifacts_path / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _jsonl_path(settings: Optional[Settings] = None) -> Path:
    return _logs_dir(settings) / "events.jsonl"


def _sqlite_path(settings: Optional[Settings] = None) -> Path:
    return _logs_dir(settings) / "events.sqlite"


def _connect(settings: Optional[Settings] = None) -> sqlite3.Connection:
    connection = sqlite3.connect(_sqlite_path(settings))
    connection.executescript(_SCHEMA)
    return connection


def _enriched_event_dict(event: StudyEvent, settings: Optional[Settings] = None) -> Dict[str, object]:
    payload = event.model_dump(mode="json")
    payload["version_context"] = build_version_context(settings)
    return payload


def append_event(event: StudyEvent, settings: Optional[Settings] = None) -> Dict[str, object]:
    settings = settings or get_settings()
    record = _enriched_event_dict(event, settings)

    jsonl_path = _jsonl_path(settings)
    with jsonl_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")

    with _connect(settings) as connection:
        connection.execute(
            """
            INSERT INTO study_events
            (event_type, session_id, participant_id, study_id, timestamp, event_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_type.value,
                event.session_id,
                event.participant_id,
                event.study_id,
                event.timestamp.isoformat(),
                json.dumps(record),
            ),
        )
        connection.commit()
    return record


def list_sessions(settings: Optional[Settings] = None) -> List[Dict[str, object]]:
    with _connect(settings) as connection:
        rows = connection.execute(
            """
            SELECT session_id, participant_id, study_id, MIN(timestamp) AS started_at,
                   MAX(timestamp) AS last_event_at, COUNT(*) AS event_count
            FROM study_events
            WHERE session_id IS NOT NULL
            GROUP BY session_id, participant_id, study_id
            ORDER BY last_event_at DESC
            """
        ).fetchall()

    return [
        {
            "session_id": row[0],
            "participant_id": row[1],
            "study_id": row[2],
            "started_at": row[3],
            "last_event_at": row[4],
            "event_count": row[5],
        }
        for row in rows
    ]


def load_session_events(session_id: str, settings: Optional[Settings] = None) -> List[Dict[str, object]]:
    with _connect(settings) as connection:
        rows = connection.execute(
            """
            SELECT event_json FROM study_events
            WHERE session_id = ?
            ORDER BY timestamp ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]
