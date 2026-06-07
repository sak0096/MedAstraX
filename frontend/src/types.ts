export type ExperimentalCondition = "baseline" | "xai" | "llm";

export interface ApiMeta {
  prototype_phase: string;
  experimental_condition: ExperimentalCondition;
  data_ready: boolean;
  models_ready: boolean;
  predictions_ready: boolean;
  explanations_ready: boolean;
  instrumentation_enabled: boolean;
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
}
