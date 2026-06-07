import Plot from "react-plotly.js";
import { useMemo, useState } from "react";
import type {
  BeneficiaryDetail,
  BeneficiaryExplanation,
  DisclosureLevel,
  RiskTargetShort,
} from "../types";
import {
  disclosureTopK,
  featureLabel,
  formatShapValue,
  getFeatureContext,
  groupContributorsByTarget,
  isEquityFeature,
} from "../utils/xai";
import { StabilityBadge } from "./StabilityBadge";

interface ExplanationPanelProps {
  explanation: BeneficiaryExplanation | null;
  detail: BeneficiaryDetail | null;
  loading: boolean;
  unavailable: boolean;
  targets: RiskTargetShort[];
}

const chartLayout = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { l: 120, r: 16, t: 8, b: 24 },
  font: { family: "IBM Plex Sans, sans-serif", color: "#1f2937", size: 11 },
};

const TARGET_LABELS: Record<RiskTargetShort, string> = {
  hospitalization: "Hospitalization",
  high_utilization: "High utilization",
  elevated_cost: "Elevated cost",
};

export function ExplanationPanel({
  explanation,
  detail,
  loading,
  unavailable,
  targets,
}: ExplanationPanelProps) {
  const [disclosure, setDisclosure] = useState<DisclosureLevel>("concise");
  const [activeTarget, setActiveTarget] = useState<RiskTargetShort>("hospitalization");
  const topK = disclosureTopK(disclosure);

  const grouped = useMemo(
    () => groupContributorsByTarget(explanation?.contributors ?? [], topK),
    [explanation, topK],
  );

  const activeContributors = grouped[activeTarget] ?? [];

  const stabilityForTarget = explanation?.stability.find(
    (item) => item.target === `next_year_${activeTarget}`,
  );

  if (loading) {
    return (
      <section className="xai-section">
        <h3>Local explanations</h3>
        <p className="detail-loading">Loading SHAP contributors…</p>
      </section>
    );
  }

  if (unavailable) {
    return (
      <section className="xai-section">
        <h3>Local explanations</h3>
        <p className="xai-empty">
          No cached explanation for this beneficiary-year. Re-run the explainability pipeline or
          select a beneficiary with SHAP artifacts.
        </p>
      </section>
    );
  }

  if (!explanation) return null;

  return (
    <section className="xai-section">
      <div className="xai-section-header">
        <div>
          <h3>Local explanations</h3>
          <p className="panel-subtitle">
            Top feature contributors with direction, stability, and source values.
          </p>
        </div>
        <div className="disclosure-toggle" role="group" aria-label="Explanation detail level">
          <button
            type="button"
            className={`target-button${disclosure === "concise" ? " active" : ""}`}
            onClick={() => setDisclosure("concise")}
          >
            Concise (top 3)
          </button>
          <button
            type="button"
            className={`target-button${disclosure === "expanded" ? " active" : ""}`}
            onClick={() => setDisclosure("expanded")}
          >
            Expanded (top 5)
          </button>
        </div>
      </div>

      <div className="target-switcher compact" role="tablist" aria-label="Explanation target">
        {targets.map((target) => (
          <button
            key={target}
            type="button"
            role="tab"
            aria-selected={activeTarget === target}
            className={`target-button${activeTarget === target ? " active" : ""}`}
            onClick={() => setActiveTarget(target)}
          >
            {TARGET_LABELS[target]}
          </button>
        ))}
      </div>

      <div className="stability-row">
        <span>Explanation stability</span>
        {stabilityForTarget ? (
          <StabilityBadge
            badge={stabilityForTarget.stability_badge}
            score={stabilityForTarget.stability_score}
          />
        ) : (
          <span className="muted">—</span>
        )}
      </div>

      {activeContributors.length > 0 ? (
        <>
          <Plot
            data={[
              {
                type: "bar",
                orientation: "h",
                y: [...activeContributors].reverse().map((row) => featureLabel(row.feature)),
                x: [...activeContributors].reverse().map((row) => row.shap_value),
                marker: {
                  color: [...activeContributors]
                    .reverse()
                    .map((row) =>
                      row.direction === "increases_risk" ? "#e76f51" : "#2a9d8f",
                    ),
                },
                hovertemplate: "%{y}<br>SHAP: %{x:.3f}<extra></extra>",
              },
            ]}
            layout={{
              ...chartLayout,
              height: Math.max(180, activeContributors.length * 42),
              xaxis: { title: "SHAP value", zeroline: true, zerolinecolor: "#9ca3af" },
              yaxis: { automargin: true },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />

          <ul className="contributor-list">
            {activeContributors.map((contributor) => {
              const context = getFeatureContext(contributor.feature, detail);
              return (
                <li key={`${contributor.target}-${contributor.feature}-${contributor.rank}`}>
                  <div className="contributor-head">
                    <strong>{featureLabel(contributor.feature)}</strong>
                    <span className={`direction-pill ${contributor.direction}`}>
                      {contributor.direction === "increases_risk" ? "↑ risk" : "↓ risk"}
                    </span>
                    {isEquityFeature(contributor.feature) ? (
                      <span className="fairness-cue" title="Equity-relevant feature">
                        Fairness cue
                      </span>
                    ) : null}
                  </div>
                  <div className="contributor-meta">
                    <span>SHAP {formatShapValue(contributor.shap_value)}</span>
                    {context ? <span className="context-preview">Value: {context}</span> : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      ) : (
        <p className="xai-empty">No contributors available for this target.</p>
      )}
    </section>
  );
}
