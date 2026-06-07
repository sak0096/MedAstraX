"""Event logging for user-study instrumentation (Phase 8)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from hc_analytics.config import ExperimentalCondition


class EventType(str, Enum):
    SESSION_START = "session_start"
    FILTER_CHANGE = "filter_change"
    DRILL_DOWN = "drill_down"
    EXPLANATION_VIEW = "explanation_view"
    QUERY_SUBMIT = "query_submit"
    QUERY_CONFIRM = "query_confirm"
    EXPORT = "export"


class StudyEvent(BaseModel):
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    participant_id: Optional[str] = None
    session_id: Optional[str] = None
    study_id: Optional[str] = None
    condition: Optional[ExperimentalCondition] = None
    task_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


def log_event(event: StudyEvent) -> None:
    """Persist event to artifacts/logs (stub)."""
    # Phase 8: append to JSONL or SQLite store
    _ = event
