from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from hc_analytics.api.data_access import load_cohort_summary_payload

router = APIRouter(prefix="/api/cohort", tags=["cohort"])


@router.get("/summary")
def cohort_summary() -> Dict[str, Any]:
    return load_cohort_summary_payload()
