export type ExperimentalCondition = "baseline" | "xai" | "llm";

export type StudyEventType =
  | "session_start"
  | "filter_change"
  | "drill_down"
  | "explanation_view"
  | "explanation_toggle"
  | "evidence_link_open"
  | "evidence_dwell"
  | "query_submit"
  | "query_confirm"
  | "query_reject"
  | "query_revise"
  | "task_start"
  | "task_initial_response"
  | "task_response"
  | "comprehension_complete"
  | "export"
  | "latency";

export type RiskConfidence = "normal" | "low" | "high";

export interface StudyContextPayload {
  case_id?: string | null;
  active_manipulations?: string[];
  risk_confidence?: Record<string, RiskConfidence>;
  manipulation_applied?: string[];
}

export interface StudyCaseRef {
  case_id: string;
  label: string;
  bene_id: string;
  analytic_year: string;
}

export interface ComprehensionQuestion {
  question_id: string;
  prompt: string;
  choices: string[];
  correct_index: number;
}

export interface StudyTaskDefinition {
  task_id: string;
  study: "study1" | "study2";
  title: string;
  time_limit_min: number;
  instructions: string;
  response_type: string;
  requires_cases: string[];
  manipulation_slot?: "study1" | "study2" | null;
  conditions: string[];
  suggested_query?: string | null;
  sequential_judgment?: boolean;
}

export interface StudySession {
  participant_id: string;
  study_mode_enabled: boolean;
  assignments: Record<string, string>;
  condition_order?: Record<string, string[]>;
  manipulation_catalog: Record<string, string>;
  task_sets: Record<string, string[]>;
  cases: StudyCaseRef[];
  case_set?: string;
  case_set_by_condition?: Record<string, string>;
  recommended_first_condition?: string | null;
  priority_rule?: { description?: string; weights?: Record<string, number> };
  comprehension?: {
    pass_threshold?: number;
    questions?: ComprehensionQuestion[];
  };
  comprehension_study2?: {
    pass_threshold?: number;
    questions?: ComprehensionQuestion[];
  };
}

export interface OutreachRecommendation {
  rule_description: string;
  case_ids: string[];
  priority_scores: Record<string, number>;
  correct_ranking: string[];
  recommended_ranking: string[];
  manipulated: boolean;
  rationale: string;
}

export interface ApiMeta {
  prototype_phase: string;
  experimental_condition: ExperimentalCondition;
  data_ready: boolean;
  models_ready: boolean;
  predictions_ready: boolean;
  explanations_ready: boolean;
  language_ready: boolean;
  llm_configured: boolean;
  instrumentation_enabled: boolean;
  study_mode_enabled: boolean;
}

export interface EvidenceClaim {
  statement: string;
  source_fields: string[];
  shap_feature?: string | null;
  shap_value?: number | null;
}

export interface GroundedExplanationPayload {
  beneficiary_id?: string | null;
  cohort_id?: string | null;
  claims: EvidenceClaim[];
  fallback?: string | null;
}

export interface GroundedSummary {
  bene_id: string;
  analytic_year: number;
  narrative: string;
  provider: string;
  grounded: GroundedExplanationPayload;
  target_summaries: Array<{
    target: string;
    target_short: string;
    risk_score: number | null;
    stability_badge: string;
    top_features: string[];
  }>;
  study_context?: StudyContextPayload;
}

export interface InterpretedQuery {
  query_id: string;
  natural_language: string;
  action: "list_beneficiaries" | "cohort_summary";
  parameters: Record<string, unknown>;
  confirmation_message: string;
  requires_confirmation: boolean;
}

export interface QueryResult {
  query_id: string;
  action: "list_beneficiaries" | "cohort_summary";
  natural_language: string;
  parameters: Record<string, unknown>;
  row_count: number;
  rows: BeneficiaryRow[];
  cohort_summary?: CohortSummary | null;
  grounded_narrative?: string | null;
  claims: EvidenceClaim[];
  fallback?: string | null;
  cached: boolean;
}

export interface CohortSummary {
  beneficiary_years: number;
  distinct_beneficiaries: number;
  analytic_years: number[];
  avg_total_claims: number;
  avg_total_payment_amt: number;
  hospitalization_rate_next_year: number;
  by_age_group: Array<{
    age_group: string;
    beneficiary_years: number;
    avg_total_claims: number;
    hospitalization_rate_next_year: number;
  }>;
  by_chronic_condition: Array<{
    condition: string;
    field: string;
    prevalence: number;
    count: number;
  }>;
  utilization_distribution: Array<{
    bucket: string;
    beneficiary_years: number;
  }>;
  cost_distribution: Array<{
    bucket: string;
    beneficiary_years: number;
  }>;
}

export interface BeneficiaryRow {
  bene_id: string;
  analytic_year: number;
  age: number | null;
  sex: string | null;
  state_code: string | null;
  total_claims: number | null;
  total_payment_amt: number | null;
  chronic_condition_count: number | null;
  hospitalization_risk: number | null;
  high_utilization_risk: number | null;
  elevated_cost_risk: number | null;
}

export type RiskTargetShort = "hospitalization" | "high_utilization" | "elevated_cost";

export type StabilityBadge = "green" | "yellow" | "red";

export type DisclosureLevel = "concise" | "expanded";

export interface ExplanationsMeta {
  explanations_ready: boolean;
  targets: string[];
  target_short_names: RiskTargetShort[];
  equity_relevant_features: string[];
  disclosure_levels: Record<DisclosureLevel, number>;
  schema_version?: string;
  model_family?: string;
  top_k?: number;
  row_count?: number;
  stability_method?: string;
}

export interface GlobalImportance {
  target: string;
  target_short: RiskTargetShort;
  model_family: string;
  importance: Array<{
    feature: string;
    mean_abs_shap: number;
    rank: number;
  }>;
}

export interface ExplanationContributor {
  feature: string;
  shap_value: number;
  direction: "increases_risk" | "decreases_risk";
  rank: number;
  target: string;
  target_short: RiskTargetShort;
  stability_badge: StabilityBadge;
  stability_score: number;
}

export interface BeneficiaryExplanation {
  bene_id: string;
  analytic_year: number;
  contributors: ExplanationContributor[];
  stability: Array<{
    target: string;
    stability_badge: StabilityBadge;
    stability_score: number;
  }>;
  study_context?: StudyContextPayload;
}

export interface BeneficiaryDetail {
  bene_id: string;
  analytic_year: number | null;
  demographics: {
    age: number | null;
    sex: string | null;
    race: string | null;
    state_code: string | null;
    esrd_ind: string | null;
  };
  risk_scores: Record<string, number | null>;
  utilization: Record<string, number | null>;
  prescriptions: Record<string, number | null>;
  diagnosis: {
    distinct_diagnosis_count: number | null;
    chronic_condition_count: number | null;
    chronic_conditions: Array<{ field: string; label: string }>;
    chronic_flags: Record<string, number | null>;
  };
  labels: Record<string, number | null>;
  model_version: string | null;
  history: BeneficiaryRow[];
  study_context?: StudyContextPayload;
}
