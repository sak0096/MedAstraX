import type { BeneficiaryRow, CohortSummary } from "../types";
import { exportCohortPdf, exportRiskTableCsv } from "../utils/export";

interface ExportMenuProps {
  rows: BeneficiaryRow[];
  summary: CohortSummary | null;
}

export function ExportMenu({ rows, summary }: ExportMenuProps) {
  return (
    <div className="export-menu">
      <button
        type="button"
        className="secondary-button"
        onClick={() => exportRiskTableCsv(rows)}
        disabled={rows.length === 0}
      >
        Export risk table (CSV)
      </button>
      <button
        type="button"
        className="secondary-button"
        onClick={() => summary && exportCohortPdf(summary)}
        disabled={!summary}
      >
        Export cohort summary (PDF)
      </button>
    </div>
  );
}
