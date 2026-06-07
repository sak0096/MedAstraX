import type { BeneficiaryDetail, DisclosureLevel, ExplanationContributor } from "../types";
import { formatCurrency, formatNumber, formatSex } from "./format";

export const EQUITY_RELEVANT_FEATURES = new Set([
  "age",
  "sex",
  "race",
  "state_code",
  "esrd_ind",
]);

export const FEATURE_LABELS: Record<string, string> = {
  age: "Age",
  sex: "Sex",
  race: "Race",
  state_code: "State",
  esrd_ind: "ESRD indicator",
  inpatient_claims: "Inpatient claims",
  outpatient_claims: "Outpatient claims",
  carrier_claims: "Carrier claims",
  snf_claims: "SNF claims",
  dme_claims: "DME claims",
  hha_claims: "HHA claims",
  hospice_claims: "Hospice claims",
  total_claims: "Total claims",
  total_payment_amt: "Total payment",
  inpatient_payment_amt: "Inpatient payment",
  rx_fill_count: "Rx fill count",
  rx_unique_drugs: "Unique drugs",
  rx_days_supply: "Rx days supply",
  distinct_diagnosis_count: "Distinct diagnoses",
  has_diabetes: "Diabetes",
  has_chf: "Heart failure",
  has_copd: "COPD",
  has_ckd: "Chronic kidney disease",
  has_hypertension: "Hypertension",
  chronic_condition_count: "Chronic conditions",
  readmission_30d_count: "30-day readmissions",
};

export function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature.replace(/_/g, " ");
}

export function isEquityFeature(feature: string): boolean {
  return EQUITY_RELEVANT_FEATURES.has(feature);
}

export function disclosureTopK(level: DisclosureLevel): number {
  return level === "concise" ? 3 : 5;
}

export function groupContributorsByTarget(
  contributors: ExplanationContributor[],
  topK: number,
): Partial<Record<ExplanationContributor["target_short"], ExplanationContributor[]>> {
  const grouped: Partial<
    Record<ExplanationContributor["target_short"], ExplanationContributor[]>
  > = {};
  for (const contributor of contributors) {
    const bucket = grouped[contributor.target_short] ?? [];
    if (bucket.length < topK) {
      bucket.push(contributor);
      grouped[contributor.target_short] = bucket;
    }
  }
  return grouped;
}

export function getFeatureContext(
  feature: string,
  detail: BeneficiaryDetail | null,
): string | null {
  if (!detail) return null;

  const { demographics, utilization, prescriptions, diagnosis } = detail;
  switch (feature) {
    case "age":
      return demographics.age !== null ? `${demographics.age} years` : null;
    case "sex":
      return formatSex(demographics.sex);
    case "race":
      return demographics.race ?? null;
    case "state_code":
      return demographics.state_code ?? null;
    case "esrd_ind":
      return demographics.esrd_ind === "1" ? "Yes" : "No";
    case "total_payment_amt":
    case "inpatient_payment_amt":
      return formatCurrency(utilization[feature]);
    case "total_claims":
    case "inpatient_claims":
    case "outpatient_claims":
    case "carrier_claims":
    case "snf_claims":
    case "dme_claims":
    case "hha_claims":
    case "hospice_claims":
    case "readmission_30d_count":
      return utilization[feature] !== undefined && utilization[feature] !== null
        ? String(utilization[feature])
        : null;
    case "distinct_diagnosis_count":
      return diagnosis.distinct_diagnosis_count !== null
        ? String(diagnosis.distinct_diagnosis_count)
        : null;
    case "chronic_condition_count":
      return diagnosis.chronic_condition_count !== null
        ? String(diagnosis.chronic_condition_count)
        : null;
    case "rx_fill_count":
    case "rx_unique_drugs":
    case "rx_days_supply":
      return prescriptions[feature] !== undefined && prescriptions[feature] !== null
        ? String(prescriptions[feature])
        : null;
    default:
      if (feature.startsWith("has_")) {
        const flag = diagnosis.chronic_flags[feature];
        return flag === 1 ? "Present" : flag === 0 ? "Absent" : null;
      }
      return null;
  }
}

export function formatShapValue(value: number): string {
  return formatNumber(value, 3);
}
