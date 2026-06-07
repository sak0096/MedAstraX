import type { BeneficiaryRow, CohortSummary, ExperimentalCondition } from "../types";
import { trackEvent } from "../instrumentation/logger";
import { exportCohortPdf, exportRiskTableCsv } from "../utils/export";

interface ExportMenuProps {
  rows: BeneficiaryRow[];
  summary: CohortSummary | null;
  condition?: ExperimentalCondition;
}

export function ExportMenu({ rows, summary, condition }: ExportMenuProps) {
  return (
    <div className="export-menu">
      <button
        type="button"
        className="secondary-button"
        onClick={() => {
          exportRiskTableCsv(rows);
          void trackEvent("export", { format: "csv", row_count: rows.length }, condition);
        }}
        disabled={rows.length === 0}
      >
        Export risk table (CSV)
      </button>
      <button
        type="button"
        className="secondary-button"
        onClick={() => {
          if (!summary) return;
          exportCohortPdf(summary);
          void trackEvent("export", { format: "pdf", type: "cohort_summary" }, condition);
        }}
        disabled={!summary}
      >
        Export cohort summary (PDF)
      </button>
    </div>
  );
}
