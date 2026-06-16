from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ManipulationType = Literal[
    "inverted_shap",
    "misleading_risk",
    "false_narrative_claim",
    "incorrect_query_filter",
    "low_confidence",
]


class StudyTaskDefinition(BaseModel):
    task_id: str
    study: Literal["study1", "study2"]
    title: str
    time_limit_min: int
    instructions: str
    response_type: str
    requires_cases: List[str] = Field(default_factory=list)
    manipulation_slot: Optional[Literal["study1", "study2"]] = None
    conditions: List[str] = Field(default_factory=list)
    suggested_query: Optional[str] = None


class StudyCaseDefinition(BaseModel):
    case_id: str
    label: str
    bene_id: str
    analytic_year: int
    ground_truth: Dict[str, Any] = Field(default_factory=dict)
    manipulations: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class StudyCatalog(BaseModel):
    schema_version: str
    default_analytic_year: int
    manipulation_catalog: Dict[str, str]
    cases: List[StudyCaseDefinition]
    tasks: List[StudyTaskDefinition]
    task_sets: Dict[str, List[str]]


class StudySessionResponse(BaseModel):
    participant_id: str
    study_mode_enabled: bool
    assignments: Dict[str, str]
    manipulation_catalog: Dict[str, str]
    task_sets: Dict[str, List[str]]
    cases: List[Dict[str, str]]


class TaskResponseSubmission(BaseModel):
    participant_id: str
    session_id: str
    responses: Dict[str, Any] = Field(default_factory=dict)
    time_ms: Optional[int] = None
    notes: Optional[str] = None


class StudyContextPayload(BaseModel):
    case_id: Optional[str] = None
    active_manipulations: List[str] = Field(default_factory=list)
    risk_confidence: Dict[str, str] = Field(default_factory=dict)
    manipulation_applied: List[str] = Field(default_factory=list)
