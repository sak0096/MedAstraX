import { trackEvent } from "../instrumentation/logger";
import type { GroundedSummary } from "../types";
import { featureLabel } from "../utils/xai";

interface GroundedSummaryPanelProps {
  summary: GroundedSummary | null;
  loading: boolean;
  unavailable: boolean;
  condition?: "baseline" | "xai" | "llm";
}

export function GroundedSummaryPanel({
  summary,
  loading,
  unavailable,
  condition,
}: GroundedSummaryPanelProps) {
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
    void trackEvent(
      "evidence_link_open",
      {
        source_field: field,
        claim,
        bene_id: summary.bene_id,
        analytic_year: summary.analytic_year,
      },
      condition,
    );
  };

  return (
    <section className="llm-section">
      <div className="llm-section-header">
        <div>
          <h3>Record summary</h3>
          <p className="panel-subtitle">Written summary of the visible record. Open a source field to check a claim.</p>
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
                <span className="shap-link">
                  Also linked to {featureLabel(claim.shap_feature)}
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
