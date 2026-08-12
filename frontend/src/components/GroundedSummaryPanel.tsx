import { useEffect, useMemo, useRef, useState } from "react";
import { trackEvent } from "../instrumentation/logger";
import type { BeneficiaryDetail, GroundedSummary } from "../types";
import { featureLabel } from "../utils/xai";
import { formatCurrency, formatPercent, formatSex } from "../utils/format";

interface GroundedSummaryPanelProps {
  summary: GroundedSummary | null;
  loading: boolean;
  unavailable: boolean;
  condition?: "baseline" | "xai" | "llm";
  detail?: BeneficiaryDetail | null;
}

function fieldValue(detail: BeneficiaryDetail | null | undefined, field: string): string {
  if (!detail) return "Value unavailable — open the record panels below.";
  const demographics = detail.demographics as Record<string, unknown>;
  const utilization = detail.utilization as Record<string, unknown>;
  const diagnosis = detail.diagnosis as Record<string, unknown>;
  const prescriptions = detail.prescriptions as Record<string, unknown>;
  const risk = detail.risk_scores as Record<string, number | null>;

  if (field in demographics) {
    const value = demographics[field];
    if (field === "sex") return formatSex(value as string | null);
    return value == null ? "—" : String(value);
  }
  if (field in utilization) {
    const value = utilization[field];
    if (field.includes("payment")) return formatCurrency(value as number | null);
    return value == null ? "—" : String(value);
  }
  if (field in prescriptions) {
    const value = prescriptions[field];
    return value == null ? "—" : String(value);
  }
  if (field === "chronic_condition_count" || field === "distinct_diagnosis_count") {
    const value = diagnosis[field];
    return value == null ? "—" : String(value);
  }
  if (field.startsWith("has_")) {
    const match = detail.diagnosis.chronic_conditions.find((item) => item.field === field);
    return match ? "Flagged" : "Not flagged";
  }
  if (field in risk) {
    return formatPercent(risk[field] ?? null, 0);
  }
  if (field === "analytic_year") return String(detail.analytic_year);
  if (field === "bene_id") return detail.bene_id;
  return "See record panels for this field.";
}

export function GroundedSummaryPanel({
  summary,
  loading,
  unavailable,
  condition,
  detail = null,
}: GroundedSummaryPanelProps) {
  const dwell = useRef<{ field: string; claim: string; started: number } | null>(null);
  const [evidence, setEvidence] = useState<{
    field: string;
    claim: string;
    value: string;
    openedAt: number;
  } | null>(null);

  const flushDwell = (closedExplicitly = false) => {
    const current = dwell.current;
    if (!current || !summary) return;
    void trackEvent(
      "evidence_dwell",
      {
        source_field: current.field,
        claim: current.claim,
        duration_ms: Date.now() - current.started,
        bene_id: summary.bene_id,
        analytic_year: summary.analytic_year,
        closed_explicitly: closedExplicitly,
        evidence_panel_open: true,
      },
      condition,
    );
    dwell.current = null;
  };

  useEffect(() => () => flushDwell(), [summary, condition]);

  const evidenceOpen = useMemo(() => evidence !== null, [evidence]);

  if (loading) {
    return (
      <section className="llm-section">
        <h3>Record summary</h3>
        <p className="detail-loading">Loading record summary…</p>
      </section>
    );
  }

  if (unavailable) {
    return (
      <section className="llm-section">
        <h3>Record summary</h3>
        <p className="xai-empty">No summary is available for this beneficiary-year.</p>
      </section>
    );
  }

  if (!summary) return null;

  const fallback = summary.grounded.fallback;

  const handleEvidenceOpen = (field: string, claim: string) => {
    flushDwell(true);
    const openedAt = Date.now();
    dwell.current = { field, claim, started: openedAt };
    setEvidence({
      field,
      claim,
      value: fieldValue(detail, field),
      openedAt,
    });
    void trackEvent(
      "evidence_link_open",
      {
        source_field: field,
        claim,
        bene_id: summary.bene_id,
        analytic_year: summary.analytic_year,
        value_shown: true,
      },
      condition,
    );
  };

  const handleEvidenceClose = () => {
    flushDwell(true);
    setEvidence(null);
  };

  return (
    <section className="llm-section">
      <div className="llm-section-header">
        <div>
          <h3>Record summary</h3>
          <p className="panel-subtitle">
            Written summary of the visible record. Open a source field to inspect the stored value.
          </p>
        </div>
      </div>

      {fallback ? (
        <p className="fallback-banner">Insufficient evidence — summary withheld.</p>
      ) : (
        <p className="grounded-narrative">{summary.narrative}</p>
      )}

      <ul className="evidence-claim-list">
        {summary.grounded.claims.map((claim, index) => (
          <li key={`${claim.statement}-${index}`}>
            <p>{claim.statement}</p>
            <div className="evidence-links">
              <span>Sources:</span>
              {claim.source_fields.map((field) => (
                <button
                  key={field}
                  type="button"
                  className="evidence-link"
                  title={field}
                  onClick={() => handleEvidenceOpen(field, claim.statement)}
                >
                  {featureLabel(field)}
                </button>
              ))}
              {claim.shap_feature ? (
                <span className="shap-link">Also linked to {featureLabel(claim.shap_feature)}</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>

      {evidenceOpen && evidence ? (
        <aside className="evidence-drawer" aria-live="polite">
          <div className="evidence-drawer-header">
            <h4>Source evidence</h4>
            <button type="button" className="ghost-button" onClick={handleEvidenceClose}>
              Close
            </button>
          </div>
          <dl className="detail-grid">
            <div>
              <dt>Field</dt>
              <dd>{featureLabel(evidence.field)}</dd>
            </div>
            <div>
              <dt>Stored value</dt>
              <dd>{evidence.value}</dd>
            </div>
            <div>
              <dt>Analytic year</dt>
              <dd>{summary.analytic_year}</dd>
            </div>
            <div>
              <dt>Supports / contradicts</dt>
              <dd>{evidence.claim}</dd>
            </div>
          </dl>
        </aside>
      ) : null}
    </section>
  );
}
