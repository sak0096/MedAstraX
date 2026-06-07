import Plot from "react-plotly.js";
import type { GlobalImportance, RiskTargetShort } from "../types";
import { featureLabel, isEquityFeature } from "../utils/xai";

interface GlobalImportancePanelProps {
  importance: GlobalImportance;
  selectedTarget: RiskTargetShort;
  onTargetChange: (target: RiskTargetShort) => void;
  targets: RiskTargetShort[];
}

const chartLayout = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { l: 140, r: 16, t: 16, b: 40 },
  font: { family: "IBM Plex Sans, sans-serif", color: "#1f2937", size: 12 },
};

export function GlobalImportancePanel({
  importance,
  selectedTarget,
  onTargetChange,
  targets,
}: GlobalImportancePanelProps) {
  const topFeatures = importance.importance.slice(0, 10);
  const labels = topFeatures.map((row) => featureLabel(row.feature));
  const values = topFeatures.map((row) => row.mean_abs_shap);
  const colors = topFeatures.map((row) =>
    isEquityFeature(row.feature) ? "#7c3aed" : "#457b9d",
  );

  return (
    <section className="panel xai-panel">
      <div className="panel-header">
        <div>
          <h2>Global Feature Importance</h2>
          <p className="panel-subtitle">
            Cohort-level mean |SHAP| rankings. Purple bars flag equity-relevant features.
          </p>
        </div>
        <div className="target-switcher" role="tablist" aria-label="Risk target">
          {targets.map((target) => (
            <button
              key={target}
              type="button"
              role="tab"
              aria-selected={selectedTarget === target}
              className={`target-button${selectedTarget === target ? " active" : ""}`}
              onClick={() => onTargetChange(target)}
            >
              {target.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      <Plot
        data={[
          {
            type: "bar",
            orientation: "h",
            y: [...labels].reverse(),
            x: [...values].reverse(),
            marker: { color: [...colors].reverse() },
            hovertemplate: "%{y}<br>Mean |SHAP|: %{x:.3f}<extra></extra>",
          },
        ]}
        layout={{
          ...chartLayout,
          height: 360,
          xaxis: { title: "Mean |SHAP|" },
          yaxis: { automargin: true },
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
        useResizeHandler
      />

      <ul className="legend-list">
        <li>
          <span className="legend-swatch model" /> Model features
        </li>
        <li>
          <span className="legend-swatch equity" /> Equity-relevant feature
        </li>
      </ul>
    </section>
  );
}
