import type { BeneficiaryRow, CohortSummary } from "../types";
import { formatCurrency, formatPercent } from "./format";

function escapeCsv(value: string | number | null | undefined): string {
  const text = value === null || value === undefined ? "" : String(value);
  if (text.includes(",") || text.includes('"') || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function downloadCsv(filename: string, headers: string[], rows: Array<Array<string | number | null>>): void {
  const lines = [
    headers.join(","),
    ...rows.map((row) => row.map(escapeCsv).join(",")),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function exportRiskTableCsv(rows: BeneficiaryRow[]): void {
  downloadCsv(
    "medastrax-risk-table.csv",
    [
      "bene_id",
      "analytic_year",
      "age",
      "sex",
      "state_code",
      "total_claims",
      "total_payment_amt",
      "chronic_condition_count",
      "hospitalization_risk",
      "high_utilization_risk",
      "elevated_cost_risk",
    ],
    rows.map((row) => [
      row.bene_id,
      row.analytic_year,
      row.age,
      row.sex,
      row.state_code,
      row.total_claims,
      row.total_payment_amt,
      row.chronic_condition_count,
      row.hospitalization_risk,
      row.high_utilization_risk,
      row.elevated_cost_risk,
    ]),
  );
}

export function buildCohortReportHtml(summary: CohortSummary): string {
  const ageRows = summary.by_age_group
    .map(
      (row) =>
        `<tr><td>${row.age_group}</td><td>${row.beneficiary_years.toLocaleString()}</td><td>${row.avg_total_claims.toFixed(1)}</td><td>${formatPercent(row.hospitalization_rate_next_year)}</td></tr>`,
    )
    .join("");
  const conditionRows = summary.by_chronic_condition
    .map(
      (row) =>
        `<tr><td>${row.condition}</td><td>${row.count.toLocaleString()}</td><td>${formatPercent(row.prevalence)}</td></tr>`,
    )
    .join("");

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>MedAstraX Cohort Summary</title>
    <style>
      body { font-family: Georgia, serif; color: #1f2937; margin: 32px; }
      h1, h2 { color: #0f4c5c; }
      table { border-collapse: collapse; width: 100%; margin-bottom: 24px; }
      th, td { border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }
      th { background: #f3f4f6; }
      .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }
      .metric { border: 1px solid #d1d5db; padding: 12px; border-radius: 8px; }
      .metric strong { display: block; font-size: 1.2rem; }
    </style>
  </head>
  <body>
    <h1>MedAstraX Cohort Summary</h1>
    <p>Baseline dashboard export generated ${new Date().toLocaleString()}</p>
    <div class="metrics">
      <div class="metric"><span>Beneficiary-years</span><strong>${summary.beneficiary_years.toLocaleString()}</strong></div>
      <div class="metric"><span>Distinct beneficiaries</span><strong>${summary.distinct_beneficiaries.toLocaleString()}</strong></div>
      <div class="metric"><span>Next-year hospitalization rate</span><strong>${formatPercent(summary.hospitalization_rate_next_year)}</strong></div>
      <div class="metric"><span>Avg claims</span><strong>${summary.avg_total_claims.toFixed(1)}</strong></div>
      <div class="metric"><span>Avg payment</span><strong>${formatCurrency(summary.avg_total_payment_amt)}</strong></div>
      <div class="metric"><span>Years covered</span><strong>${summary.analytic_years.join(", ")}</strong></div>
    </div>
    <h2>By Age Group</h2>
    <table><thead><tr><th>Age group</th><th>Beneficiary-years</th><th>Avg claims</th><th>Hospitalization rate</th></tr></thead><tbody>${ageRows}</tbody></table>
    <h2>Chronic Conditions</h2>
    <table><thead><tr><th>Condition</th><th>Count</th><th>Prevalence</th></tr></thead><tbody>${conditionRows}</tbody></table>
  </body>
</html>`;
}

export function exportCohortPdf(summary: CohortSummary): void {
  const reportWindow = window.open("", "_blank", "noopener,noreferrer,width=900,height=700");
  if (!reportWindow) return;
  reportWindow.document.write(buildCohortReportHtml(summary));
  reportWindow.document.close();
  reportWindow.focus();
  reportWindow.print();
}
