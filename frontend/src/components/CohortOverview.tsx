import Plot from "react-plotly.js";
import type { CohortSummary } from "../types";
import { formatCurrency, formatPercent } from "../utils/format";

interface CohortOverviewProps {
  summary: CohortSummary;
}

const chartLayout = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { l: 40, r: 16, t: 24, b: 40 },
  font: { family: "IBM Plex Sans, sans-serif", color: "#1f2937", size: 12 },
};

export function CohortOverview({ summary }: CohortOverviewProps) {
  const ageGroups = summary.by_age_group.map((row) => row.age_group);
  const ageCounts = summary.by_age_group.map((row) => row.beneficiary_years);
  const ageHospitalization = summary.by_age_group.map(
    (row) => row.hospitalization_rate_next_year * 100,
  );

  const conditions = summary.by_chronic_condition.map((row) => row.condition);
  const conditionPrevalence = summary.by_chronic_condition.map((row) => row.prevalence * 100);

  const utilizationBuckets = summary.utilization_distribution.map((row) => row.bucket);
  const utilizationCounts = summary.utilization_distribution.map((row) => row.beneficiary_years);

  const costBuckets = summary.cost_distribution.map((row) => row.bucket);
  const costCounts = summary.cost_distribution.map((row) => row.beneficiary_years);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Cohort Overview</h2>
          <p className="panel-subtitle">
            Population-level utilization, diagnosis burden, and cost patterns.
          </p>
        </div>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <span>Beneficiary-years</span>
          <strong>{summary.beneficiary_years.toLocaleString()}</strong>
        </article>
        <article className="metric-card">
          <span>Distinct beneficiaries</span>
          <strong>{summary.distinct_beneficiaries.toLocaleString()}</strong>
        </article>
        <article className="metric-card">
          <span>Avg claims / year</span>
          <strong>{summary.avg_total_claims.toFixed(1)}</strong>
        </article>
        <article className="metric-card">
          <span>Avg payment / year</span>
          <strong>{formatCurrency(summary.avg_total_payment_amt)}</strong>
        </article>
        <article className="metric-card">
          <span>Next-year hospitalization</span>
          <strong>{formatPercent(summary.hospitalization_rate_next_year)}</strong>
        </article>
      </div>

      <div className="chart-grid">
        <article className="chart-card">
          <h3>Age distribution</h3>
          <Plot
            data={[
              {
                type: "bar",
                x: ageGroups,
                y: ageCounts,
                marker: { color: "#2a9d8f" },
              },
            ]}
            layout={{
              ...chartLayout,
              height: 280,
              xaxis: { title: "Age group" },
              yaxis: { title: "Beneficiary-years" },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        </article>

        <article className="chart-card">
          <h3>Hospitalization rate by age</h3>
          <Plot
            data={[
              {
                type: "scatter",
                mode: "lines+markers",
                x: ageGroups,
                y: ageHospitalization,
                line: { color: "#e76f51", width: 3 },
                marker: { size: 8 },
              },
            ]}
            layout={{
              ...chartLayout,
              height: 280,
              xaxis: { title: "Age group" },
              yaxis: { title: "Rate (%)", ticksuffix: "%" },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        </article>

        <article className="chart-card">
          <h3>Chronic condition prevalence</h3>
          <Plot
            data={[
              {
                type: "bar",
                orientation: "h",
                y: conditions,
                x: conditionPrevalence,
                marker: { color: "#457b9d" },
              },
            ]}
            layout={{
              ...chartLayout,
              height: 280,
              xaxis: { title: "Prevalence (%)", ticksuffix: "%" },
              yaxis: { automargin: true },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        </article>

        <article className="chart-card">
          <h3>Utilization and cost distribution</h3>
          <Plot
            data={[
              {
                type: "bar",
                name: "Claims bucket",
                x: utilizationBuckets,
                y: utilizationCounts,
                marker: { color: "#6d597a" },
              },
              {
                type: "bar",
                name: "Cost bucket",
                x: costBuckets,
                y: costCounts,
                marker: { color: "#b56576" },
              },
            ]}
            layout={{
              ...chartLayout,
              height: 280,
              barmode: "group",
              xaxis: { title: "Bucket" },
              yaxis: { title: "Beneficiary-years" },
              legend: { orientation: "h", y: 1.15 },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        </article>
      </div>
    </section>
  );
}
