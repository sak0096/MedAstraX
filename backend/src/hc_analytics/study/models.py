from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ManipulationType = Literal[
    "incorrect_outreach_recommendation",
    "false_narrative_claim",
    "incorrect_query_filter",
    "incorrect_query_analytic_year",
    "omitted_query_threshold",
    # Exploratory / deprecated — not assigned in v2 pools.
    "inverted_shap",
    "misleading_risk",
    "low_confidence",
]


class PriorityRuleDefinition(BaseModel):
    description: str
    weights: Dict[str, float] = Field(default_factory=dict)


class ComprehensionQuestion(BaseModel):
    question_id: str
    prompt: str
    choices: List[str]
    correct_index: int


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
    sequential_judgment: bool = False


class StudyCaseDefinition(BaseModel):
    case_id: str
    label: str
    bene_id: str
    analytic_year: int
    case_set: str = "shared"
    ground_truth: Dict[str, Any] = Field(default_factory=dict)
    manipulations: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class StudyCatalog(BaseModel):
    schema_version: str
    default_analytic_year: int
    manipulation_catalog: Dict[str, str]
    priority_rule: PriorityRuleDefinition = Field(
        default_factory=lambda: PriorityRuleDefinition(description="", weights={})
    )
    comprehension: Dict[str, Any] = Field(default_factory=dict)
    comprehension_study2: Dict[str, Any] = Field(default_factory=dict)
    case_sets: Dict[str, List[str]] = Field(default_factory=dict)
    cases: List[StudyCaseDefinition]
    tasks: List[StudyTaskDefinition]
    task_sets: Dict[str, List[str]]


class StudySessionResponse(BaseModel):
    participant_id: str
    study_mode_enabled: bool
    assignments: Dict[str, str]
    condition_order: Dict[str, List[str]] = Field(default_factory=dict)
    manipulation_catalog: Dict[str, str]
    task_sets: Dict[str, List[str]]
    cases: List[Dict[str, str]]
    case_set: str = "alpha"
    case_set_by_condition: Dict[str, str] = Field(default_factory=dict)
    recommended_first_condition: Optional[str] = None
    priority_rule: Dict[str, Any] = Field(default_factory=dict)
    comprehension: Dict[str, Any] = Field(default_factory=dict)
    comprehension_study2: Dict[str, Any] = Field(default_factory=dict)


class TaskResponseSubmission(BaseModel):
    participant_id: str
    session_id: str
    trial_id: Optional[str] = None
    phase: Literal["initial", "final", "single"] = "single"
    responses: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[int] = Field(default=None, ge=1, le=7)
    reliance_source: Optional[str] = None
    time_ms: Optional[int] = None
    notes: Optional[str] = None


class ComprehensionSubmission(BaseModel):
    participant_id: str
    session_id: str
    answers: Dict[str, int] = Field(default_factory=dict)
    study: Optional[Literal["study1", "study2"]] = None


class StudyContextPayload(BaseModel):
    case_id: Optional[str] = None
    active_manipulations: List[str] = Field(default_factory=list)
    risk_confidence: Dict[str, str] = Field(default_factory=dict)
    manipulation_applied: List[str] = Field(default_factory=list)
    trial_id: Optional[str] = None
    manipulation_type: Optional[str] = None
    ground_truth_id: Optional[str] = None
