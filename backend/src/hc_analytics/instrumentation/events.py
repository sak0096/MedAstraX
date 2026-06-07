"""Event logging for user-study instrumentation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from hc_analytics.config import ExperimentalCondition, get_settings


class EventType(str, Enum):
    SESSION_START = "session_start"
    FILTER_CHANGE = "filter_change"
    DRILL_DOWN = "drill_down"
    EXPLANATION_VIEW = "explanation_view"
    QUERY_SUBMIT = "query_submit"
    QUERY_CONFIRM = "query_confirm"
    EXPORT = "export"
    LATENCY = "latency"


class StudyEvent(BaseModel):
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    participant_id: Optional[str] = None
    session_id: Optional[str] = None
    study_id: Optional[str] = None
    condition: Optional[ExperimentalCondition] = None
    task_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


def log_event(event: StudyEvent) -> Dict[str, object]:
    settings = get_settings()
    if not settings.log_events:
        return event.model_dump(mode="json")

    if event.study_id is None:
        event.study_id = settings.study_id
    if event.condition is None:
        event.condition = settings.experimental_condition

    from hc_analytics.instrumentation.store import append_event

    return append_event(event, settings=settings)
