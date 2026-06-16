from __future__ import annotations

from typing import Optional

from fastapi import Header

from hc_analytics.config import Settings, get_settings
from hc_analytics.study.session import active_manipulations_for_task


class StudyRequestContext:
    def __init__(
        self,
        *,
        participant_id: Optional[str],
        task_id: Optional[str],
        session_id: Optional[str],
        settings: Settings,
    ) -> None:
        self.participant_id = participant_id
        self.task_id = task_id
        self.session_id = session_id
        self.settings = settings
        self.study_mode = settings.study_mode

    @property
    def active_manipulations(self) -> list[str]:
        return active_manipulations_for_task(
            self.participant_id,
            self.task_id,
            settings=self.settings,
        )


def get_study_context(
    x_participant_id: Optional[str] = Header(default=None, alias="X-Participant-Id"),
    x_study_task_id: Optional[str] = Header(default=None, alias="X-Study-Task-Id"),
    x_study_session_id: Optional[str] = Header(default=None, alias="X-Study-Session-Id"),
) -> StudyRequestContext:
    settings = get_settings()
    return StudyRequestContext(
        participant_id=x_participant_id,
        task_id=x_study_task_id,
        session_id=x_study_session_id,
        settings=settings,
    )
