import type { ExperimentalCondition } from "../types";

export const CONDITION_COPY: Record<
  ExperimentalCondition,
  { title: string; subtitle: string }
> = {
  baseline: {
    title: "Provider Analytics Dashboard",
    subtitle:
      "Baseline control condition — cohort analytics and operational risk scores without explanation UI.",
  },
  xai: {
    title: "XAI-Augmented Analytics Dashboard",
    subtitle:
      "Visual explainability condition — SHAP local/global views, stability badges, and layered disclosure.",
  },
  llm: {
    title: "LLM-Augmented Analytics Dashboard",
    subtitle:
      "Grounded language condition — evidence-linked summaries and natural-language querying (Phase 7).",
  },
};
