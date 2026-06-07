import type { GroundedSummary } from "../types";
import { featureLabel } from "../utils/xai";

interface GroundedSummaryPanelProps {
  summary: GroundedSummary | null;
  loading: boolean;
  unavailable: boolean;
}

export function GroundedSummaryPanel({
  summary,
  loading,
  unavailable,
}: GroundedSummaryPanelProps) {
  if (loading) {
    return (
      <section className="llm-section">
        <h3>Grounded summary</h3>
        <p className="detail-loading">Generating evidence-linked narrative…</p>
      </section>
    );
  }

  if (unavailable) {
    return (
      <section className="llm-section">
        <h3>Grounded summary</h3>
        <p className="xai-empty">
          No evidence bundle available for this beneficiary-year. Run the explainability pipeline
          to enable grounded summaries.
        </p>
      </section>
    );
  }

  if (!summary) return null;

  const fallback = summary.grounded.fallback;

  return (
    <section className="llm-section">
      <div className="llm-section-header">
        <div>
          <h3>Grounded summary</h3>
          <p className="panel-subtitle">
            Template narrative mapped to verified SHAP evidence ({summary.provider} provider).
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
                <button key={field} type="button" className="evidence-link" title={field}>
                  {featureLabel(field)}
                </button>
              ))}
              {claim.shap_feature ? (
                <span className="shap-link">
                  SHAP {claim.shap_value !== undefined && claim.shap_value !== null
                    ? claim.shap_value.toFixed(3)
                    : "—"}{" "}
                  on {featureLabel(claim.shap_feature)}
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
