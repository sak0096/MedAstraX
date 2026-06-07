from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from hc_analytics.language.grounding import EvidenceClaim, GroundedExplanation

QueryAction = Literal["list_beneficiaries", "cohort_summary"]


class InterpretedQuery(BaseModel):
    query_id: str
    natural_language: str
    action: QueryAction
    parameters: Dict[str, Any] = Field(default_factory=dict)
    confirmation_message: str
    requires_confirmation: bool = True


class QueryInterpretRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)


class QueryExecuteRequest(BaseModel):
    query_id: str
    confirmed: bool = False


class QueryResult(BaseModel):
    query_id: str
    action: QueryAction
    natural_language: str
    parameters: Dict[str, Any]
    row_count: int = 0
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    cohort_summary: Optional[Dict[str, Any]] = None
    grounded_narrative: Optional[str] = None
    claims: List[EvidenceClaim] = Field(default_factory=list)
    fallback: Optional[str] = None
    cached: bool = False


class GroundedSummaryResponse(BaseModel):
    bene_id: str
    analytic_year: int
    narrative: str
    provider: str
    grounded: GroundedExplanation
    target_summaries: List[Dict[str, Any]] = Field(default_factory=list)
