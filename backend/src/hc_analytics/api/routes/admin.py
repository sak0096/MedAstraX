"""Research administration routes.

Production requires a validated Entra access token with the configured app
role. Local tests use HC_ADMIN_TOKEN. Responses never include launch secrets.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from hc_analytics.config import get_settings
from hc_analytics.persistence.repository import StateConflict, StudyRepository, StudyStoreError
from hc_analytics.security.auth import require_admin
from hc_analytics.security.redaction import redact_mapping

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _repository():
    settings = get_settings()
    try:
        return StudyRepository.from_settings(settings)
    except StudyStoreError as error:
        raise HTTPException(status_code=503, detail="Study state is unavailable.") from error


@router.get("/enrollments/{participant_code}")
def read_enrollment(
    participant_code: str,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    require_admin(authorization, get_settings())
    record = _repository().get_enrollment_by_code(participant_code)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown participant code.")
    return redact_mapping(
        {
            "participant_code": record["participant_code"],
            "namespace": record["namespace"],
            "study": record["study"],
            "status": record["status"],
            "stage": record["stage"],
            "condition_order": record["condition_order"],
            "error_slots": record["error_slots"],
            "exit_reason": record["exit_reason"],
            "payment_stage": record["payment_stage"],
            "payment_amount_cents": record["payment_amount_cents"],
            "retention_choice": record["retention_choice"],
            "is_pilot": record["is_pilot"],
            "recruitment_stage": record["recruitment_stage"],
            "confirmatory_eligible": record["confirmatory_eligible"],
            "qualtrics_deletion": "not_requested",
        }
    )


@router.post("/participants/{participant_code}/deletion")
def delete_participant(
    participant_code: str,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    require_admin(authorization, get_settings())
    try:
        result = _repository().delete_participant(participant_code)
    except StateConflict as error:
        raise HTTPException(status_code=404, detail="Unknown participant code.") from error
    except StudyStoreError as error:
        raise HTTPException(status_code=503, detail="Study state is unavailable.") from error
    return result


@router.post("/deletions/reapply")
def reapply_deletions(authorization: Optional[str] = Header(default=None)) -> dict:
    require_admin(authorization, get_settings())
    count = _repository().reapply_deletions()
    return {"reapplied": count}
