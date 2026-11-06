from __future__ import annotations

from typing import Optional

from fastapi import Header, Request

from hc_analytics.config import ExperimentalCondition, Settings, get_settings
from hc_analytics.study.session import active_manipulations_for_task


def parse_condition(value: Optional[str], settings: Settings) -> ExperimentalCondition:
    if value in {item.value for item in ExperimentalCondition}:
        return ExperimentalCondition(value)
    return settings.experimental_condition


def parse_study_arm(value: Optional[str]) -> Optional[str]:
    if value in {"study1", "study2"}:
        return value
    return None


class StudyRequestContext:
    def __init__(
        self,
        *,
        participant_id: Optional[str],
        task_id: Optional[str],
        session_id: Optional[str],
        condition: Optional[str],
        study: Optional[str],
        settings: Settings,
    ) -> None:
        self.participant_id = participant_id
        self.task_id = task_id
        self.session_id = session_id
        self.condition = parse_condition(condition, settings).value
        self.study = parse_study_arm(study)
        self.settings = settings
        self.study_mode = settings.study_mode

    @property
    def experimental_condition(self) -> ExperimentalCondition:
        return parse_condition(self.condition, self.settings)

    @property
    def active_manipulations(self) -> list[str]:
        return active_manipulations_for_task(
            self.participant_id,
            self.task_id,
            settings=self.settings,
            condition=self.condition,
        )


def _session_binding(request: Request, settings: Settings) -> Optional[dict]:
    cookie = request.cookies.get("mx_session")
    if not cookie and not settings.strict_sessions:
        return None
    if not cookie and settings.strict_sessions:
        return {"anonymous": True}
    from hc_analytics.persistence.repository import StudyRepository, StudyStoreError

    try:
        bound = StudyRepository.from_settings(settings).get_active_session(cookie or "")
    except StudyStoreError:
        return {"anonymous": True} if settings.strict_sessions else None
    if bound is None and settings.strict_sessions:
        return {"anonymous": True}
    return bound


def get_study_context(
    request: Request,
    x_participant_id: Optional[str] = Header(default=None, alias="X-Participant-Id"),
    x_study_task_id: Optional[str] = Header(default=None, alias="X-Study-Task-Id"),
    x_study_session_id: Optional[str] = Header(default=None, alias="X-Study-Session-Id"),
    x_study_condition: Optional[str] = Header(default=None, alias="X-Study-Condition"),
    x_study_arm: Optional[str] = Header(default=None, alias="X-Study-Arm"),
) -> StudyRequestContext:
    settings = get_settings()
    bound = _session_binding(request, settings)
    if bound is not None:
        if bound.get("anonymous"):
            return StudyRequestContext(
                participant_id=None,
                task_id=None,
                session_id=None,
                condition=settings.experimental_condition.value,
                study=None,
                settings=settings,
            )
        return StudyRequestContext(
            participant_id=bound["participant_code"],
            task_id=bound.get("current_task_id"),
            session_id=bound.get("session_hash"),
            condition=bound.get("condition"),
            study=bound.get("study"),
            settings=settings,
        )
    return StudyRequestContext(
        participant_id=x_participant_id,
        task_id=x_study_task_id,
        session_id=x_study_session_id,
        condition=x_study_condition,
        study=x_study_arm,
        settings=settings,
    )
