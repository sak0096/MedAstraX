import type { BeneficiaryRow, ExperimentalCondition } from "../types";
import { formatCurrency, formatPercent, riskBand } from "../utils/format";

export type SortKey =
  | "hospitalization_risk"
  | "high_utilization_risk"
  | "elevated_cost_risk"
  | "total_claims"
  | "total_payment_amt"
  | "age"
  | "analytic_year";

interface RiskTableProps {
  rows: BeneficiaryRow[];
  sortBy: SortKey;
  descending: boolean;
  loading: boolean;
  onSortChange: (sortBy: SortKey) => void;
  onRowSelect: (row: BeneficiaryRow) => void;
  selectedBeneId: string | null;
  condition?: ExperimentalCondition;
}

const columns: Array<{ key: SortKey; label: string }> = [
  { key: "analytic_year", label: "Year" },
  { key: "age", label: "Age" },
  { key: "total_claims", label: "Claims" },
  { key: "total_payment_amt", label: "Payment" },
  { key: "hospitalization_risk", label: "Hospitalization" },
  { key: "high_utilization_risk", label: "High utilization" },
  { key: "elevated_cost_risk", label: "Elevated cost" },
];

export function RiskTable({
  rows,
  sortBy,
  descending,
  loading,
  onSortChange,
  onRowSelect,
  selectedBeneId,
  condition = "baseline",
}: RiskTableProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Risk List</h2>
          <p className="panel-subtitle">
            Sortable beneficiary table for operational risk triage
            {condition === "xai"
              ? " with on-demand SHAP drill-down."
              : condition === "llm"
                ? " with grounded language summaries on drill-down."
                : " (baseline condition)."}
          </p>
        </div>
        <div className="table-meta">
          <span>{rows.length.toLocaleString()} rows</span>
          <span>
            Sorted by <strong>{sortBy}</strong> ({descending ? "desc" : "asc"})
          </span>
        </div>
      </div>

      <div className="table-wrap">
        <table className="risk-table">
          <thead>
            <tr>
              <th>Beneficiary</th>
              {columns.map((column) => (
                <th key={column.key}>
                  <button
                    type="button"
                    className={`sort-button${sortBy === column.key ? " active" : ""}`}
                    onClick={() => onSortChange(column.key)}
                  >
                    {column.label}
                    {sortBy === column.key ? (descending ? " ↓" : " ↑") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="empty-row">
                  Loading beneficiaries…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-row">
                  No beneficiaries available.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr
                  key={`${row.bene_id}-${row.analytic_year}`}
                  className={selectedBeneId === row.bene_id ? "selected" : undefined}
                  onClick={() => onRowSelect(row)}
                >
                  <td>
                    <div className="bene-cell">
                      <strong>{row.bene_id}</strong>
                      <span>
                        {row.state_code ?? "—"} · {row.chronic_condition_count ?? 0} chronic
                      </span>
                    </div>
                  </td>
                  <td>{row.analytic_year}</td>
                  <td>{row.age ?? "—"}</td>
                  <td>{row.total_claims ?? "—"}</td>
                  <td>{formatCurrency(row.total_payment_amt)}</td>
                  <td>
                    <RiskPill value={row.hospitalization_risk} />
                  </td>
                  <td>
                    <RiskPill value={row.high_utilization_risk} />
                  </td>
                  <td>
                    <RiskPill value={row.elevated_cost_risk} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RiskPill({ value }: { value: number | null }) {
  const band = riskBand(value);
  return (
    <span className={`risk-pill ${band}`}>
      {formatPercent(value, 0)}
    </span>
  );
}
