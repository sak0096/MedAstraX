from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hc_analytics.config import Settings, get_settings
from hc_analytics.instrumentation.context import build_version_context
from hc_analytics.instrumentation.store import _logs_dir, load_session_events


def pseudonymize(value: str, study_id: str) -> str:
    digest = hashlib.sha256(f"{study_id}:{value}".encode("utf-8")).hexdigest()
    return f"P-{digest[:12]}"


_SENSITIVE_KEYS = {"bene_id", "beneficiary_id", "participant_id"}


def _redact_payload(payload: Dict[str, Any], study_id: str) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SENSITIVE_KEYS and isinstance(value, str):
            redacted[f"{key}_pseudonym"] = pseudonymize(value, study_id)
            continue
        if isinstance(value, dict):
            redacted[key] = _redact_payload(value, study_id)
        else:
            redacted[key] = value
    return redacted


def _sanitize_event(event: Dict[str, Any], study_id: str) -> Dict[str, Any]:
    sanitized = dict(event)
    if sanitized.get("participant_id"):
        sanitized["participant_pseudonym"] = pseudonymize(str(sanitized["participant_id"]), study_id)
        sanitized.pop("participant_id", None)
    payload = sanitized.get("payload")
    if isinstance(payload, dict):
        sanitized["payload"] = _redact_payload(payload, study_id)
    return sanitized


def build_session_export(session_id: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    settings = settings or get_settings()
    events = load_session_events(session_id, settings=settings)
    if not events:
        raise FileNotFoundError(f"No events found for session {session_id}")

    study_id = str(events[0].get("study_id") or settings.study_id)
    sanitized_events = [_sanitize_event(event, study_id) for event in events]
    condition = events[0].get("condition")

    bundle = {
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "study_id": study_id,
        "session_id": session_id,
        "condition": condition,
        "event_count": len(sanitized_events),
        "version_context": build_version_context(settings),
        "events": sanitized_events,
    }
    return bundle


def write_session_export(session_id: str, settings: Optional[Settings] = None) -> Path:
    settings = settings or get_settings()
    bundle = build_session_export(session_id, settings=settings)
    export_dir = _logs_dir(settings) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"session_{session_id}.json"
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return path
