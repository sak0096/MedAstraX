import type { ExperimentalCondition } from "../types";

export const CONDITION_COPY: Record<
  ExperimentalCondition,
  { title: string; subtitle: string }
> = {
  baseline: {
    title: "Care Management Dashboard",
    subtitle: "Cohort analytics and operational risk scores for outreach review.",
  },
  xai: {
    title: "Care Management Dashboard",
    subtitle: "Cohort analytics, risk scores, and ranked feature-contribution views.",
  },
  llm: {
    title: "Care Management Dashboard",
    subtitle: "Cohort analytics, record summaries, and natural-language search.",
  },
};
