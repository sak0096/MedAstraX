"""Grounding constraints for LLM outputs (Phase 7)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

FALLBACK_INSUFFICIENT_EVIDENCE = "insufficient evidence"
FALLBACK_UNKNOWN = "unknown"


class EvidenceClaim(BaseModel):
    statement: str
    source_fields: List[str] = Field(min_length=1)
    shap_feature: Optional[str] = None
    shap_value: Optional[float] = None


class GroundedExplanation(BaseModel):
    beneficiary_id: Optional[str] = None
    cohort_id: Optional[str] = None
    claims: List[EvidenceClaim] = Field(default_factory=list)
    fallback: Optional[str] = None

    @classmethod
    def insufficient_evidence(cls, *, beneficiary_id: Optional[str] = None) -> GroundedExplanation:
        return cls(
            beneficiary_id=beneficiary_id,
            fallback=FALLBACK_INSUFFICIENT_EVIDENCE,
        )
