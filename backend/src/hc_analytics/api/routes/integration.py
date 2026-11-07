"""Authenticated Qualtrics launch exchange.

The browser cannot assign a participant code or assert consent. Only the
integration credential can, and only a one-time opaque token comes back.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from hc_analytics.config import get_settings
from hc_analytics.persistence.repository import (
    CapExceeded,
    DuplicateNonce,
    StateConflict,
    StudyRepository,
    StudyStoreError,
)
from hc_analytics.release import release_blockers
from hc_analytics.security.auth import require_integration

router = APIRouter(prefix="/api/integration", tags=["integration"])

_PROLIFIC_ID = re.compile(r"^[0-9a-fA-F]{24}$")


class LaunchRequest(BaseModel):
    survey_id: str = Field(min_length=1, max_length=80)
    survey_version: str = Field(min_length=1, max_length=40)
    stage: Literal["consent"]
    consent_authorized: bool
    study: Literal["study1", "study2"]
    nonce: str = Field(min_length=8, max_length=128)
    enrollment_reference: Optional[str] = Field(default=None, max_length=80)
    namespace: Literal["test", "pilot"] = "test"


class ExchangeRequest(BaseModel):
    launch_token: str = Field(min_length=16, max_length=200)


class SurveyCallbackRequest(BaseModel):
    participant_code: str = Field(pattern=r"^(TEST-\d{3}|P\d{3})$")
    survey_id: str = Field(min_length=1, max_length=80)
    survey_version: str = Field(min_length=1, max_length=40)
    callback_type: Literal[
        "post_condition_1_complete", "final_complete", "withdrawn", "technical_stop"
    ]
    nonce: str = Field(min_length=8, max_length=128)
    retention_choice: Optional[Literal["retain", "delete"]] = None


def _reject_reference(reference: Optional[str]) -> None:
    if reference is None:
        return
    if "@" in reference or "://" in reference or _PROLIFIC_ID.match(reference):
        raise HTTPException(status_code=400, detail="Enrollment reference is not usable.")


@router.post("/launch")
def launch_study(
    body: LaunchRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    settings = get_settings()
    require_integration(authorization, settings)
    if body.consent_authorized is not True:
        raise HTTPException(status_code=400, detail="Consent authorization is required.")
    _reject_reference(body.enrollment_reference)
    if body.namespace == "pilot" and not settings.recruitment_enabled:
        raise HTTPException(status_code=403, detail="Pilot recruitment is not enabled.")
    if body.namespace == "pilot" and release_blockers(settings):
        raise HTTPException(status_code=403, detail="Participant release is not ready.")
    if (
        body.namespace == "test"
        and settings.environment == "production"
        and not settings.allow_synthetic_launch
    ):
        raise HTTPException(status_code=403, detail="Synthetic launch is not enabled.")
    if settings.environment == "production" and settings.production_blockers():
        # Infrastructure and unresolved policy both keep recruitment closed.
        # Synthetic dry runs are still allowed when the database itself is ready.
        if body.namespace != "test" or not settings.allow_synthetic_launch:
            raise HTTPException(status_code=403, detail="Participant launch is not allowed.")
        if settings.infrastructure_blockers():
            raise HTTPException(status_code=503, detail="Study state is unavailable.")
    try:
        issued = StudyRepository.from_settings(settings).launch(
            namespace=body.namespace,
            study=body.study,
            survey_id=body.survey_id,
            survey_version=body.survey_version,
            nonce=body.nonce,
            enrollment_reference=body.enrollment_reference,
            environment=settings.environment,
            purpose="study_launch",
            ttl_seconds=settings.launch_ttl_seconds,
            cap_per_study=settings.enrollment_cap_per_study,
            cap_total=settings.enrollment_cap_total,
            pilot_cap_per_study=settings.pilot_cap_per_study,
            pilot_recruitment_stage=settings.pilot_recruitment_stage,
        )
    except DuplicateNonce as error:
        raise HTTPException(
            status_code=409, detail="This launch nonce was already used."
        ) from error
    except CapExceeded as error:
        raise HTTPException(status_code=409, detail="Enrollment cap reached.") from error
    except StudyStoreError as error:
        raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
    return {
        "launch_token": issued["launch_token"],
        "expires_at": issued["expires_at"],
        "exchange_path": "/api/integration/exchange",
        "study": issued["study"],
        "participant_code": issued["participant_code"],
        "resumed": issued["resumed"],
    }


@router.post("/exchange")
def exchange_launch(body: ExchangeRequest) -> JSONResponse:
    settings = get_settings()
    try:
        session = StudyRepository.from_settings(settings).consume_launch_token(
            body.launch_token,
            environment=settings.environment,
            purpose="study_launch",
            session_ttl_seconds=settings.session_ttl_seconds,
        )
    except StateConflict as error:
        raise HTTPException(status_code=401, detail="Launch credential is not usable.") from error
    except StudyStoreError as error:
        raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
    response = JSONResponse(
        {
            "study": session["study"],
            "stage": session["stage"],
            "continued": True,
        }
    )
    response.set_cookie(
        key="mx_session",
        value=session["session_cookie"],
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return response


@router.post("/survey-callback")
def survey_callback(
    body: SurveyCallbackRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """Advance only from a server-to-server, replay-safe survey callback."""
    settings = get_settings()
    require_integration(authorization, settings)
    repository = StudyRepository.from_settings(settings)
    try:
        result = repository.apply_survey_callback(
            participant_code=body.participant_code,
            callback_type=body.callback_type,
            nonce=body.nonce,
            survey_id=body.survey_id,
            survey_version=body.survey_version,
            retention_choice=body.retention_choice,
        )
        if body.callback_type == "final_complete" and body.retention_choice == "delete":
            deleted = repository.delete_participant(body.participant_code)
            result["stage"] = "deleted"
            result["deleted"] = deleted["deleted"]
            result["qualtrics_deletion_status"] = deleted["qualtrics_status"]
    except StateConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except StudyStoreError as error:
        raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
    return result
