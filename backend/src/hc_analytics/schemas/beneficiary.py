from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class BeneficiarySummary(BaseModel):
    beneficiary_id: str
    age_group: Optional[str] = None
    sex: Optional[str] = None
    risk_score: Optional[float] = None
    risk_label: Optional[str] = None
    model_version: Optional[str] = None
    top_factors: List[str] = Field(default_factory=list)
