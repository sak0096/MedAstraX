import { useCallback, useEffect, useState } from "react";
import { getBeneficiaries, getBeneficiaryDetail, getCohortSummary, getMeta } from "./api/client";
import { BeneficiaryDetail } from "./components/BeneficiaryDetail";
import { CohortOverview } from "./components/CohortOverview";
import { ExportMenu } from "./components/ExportMenu";
import { RiskTable, type SortKey } from "./components/RiskTable";
import type { ApiMeta, BeneficiaryDetail as BeneficiaryDetailType, BeneficiaryRow, CohortSummary } from "./types";

const ROW_LIMIT = 250;

export default function App() {
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const [summary, setSummary] = useState<CohortSummary | null>(null);
  const [rows, setRows] = useState<BeneficiaryRow[]>([]);
  const [detail, setDetail] = useState<BeneficiaryDetailType | null>(null);
  const [selectedBeneId, setSelectedBeneId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("hospitalization_risk");
  const [descending, setDescending] = useState(true);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [metaResponse, summaryResponse, beneficiaryResponse] = await Promise.all([
        getMeta(),
        getCohortSummary(),
        getBeneficiaries({ limit: ROW_LIMIT, sort_by: sortBy, descending }),
      ]);
      setMeta(metaResponse);
      setSummary(summaryResponse);
      setRows(beneficiaryResponse.rows);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [sortBy, descending]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const handleSortChange = (nextSortBy: SortKey) => {
    if (nextSortBy === sortBy) {
      setDescending((current) => !current);
      return;
    }
    setSortBy(nextSortBy);
    setDescending(true);
  };

  const handleRowSelect = async (row: BeneficiaryRow) => {
    setSelectedBeneId(row.bene_id);
    setDetailLoading(true);
    try {
      const response = await getBeneficiaryDetail(row.bene_id, row.analytic_year);
      setDetail(response);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load beneficiary detail.");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedBeneId(null);
    setDetail(null);
  };

  const condition = meta?.experimental_condition ?? "baseline";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">MedAstraX Research Prototype</p>
          <h1>Provider Analytics Dashboard</h1>
          <p className="header-copy">
            Baseline control condition — cohort analytics and operational risk scores without
            explanation UI.
          </p>
        </div>
        <div className="header-meta">
          <span className={`condition-badge ${condition}`}>{condition}</span>
          <span className="meta-pill">Phase {meta?.prototype_phase ?? "5"}</span>
          {meta?.predictions_ready ? (
            <span className="meta-pill ready">Predictions ready</span>
          ) : (
            <span className="meta-pill warn">Predictions missing</span>
          )}
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="toolbar">
        <ExportMenu rows={rows} summary={summary} />
        <button type="button" className="ghost-button" onClick={() => void loadDashboard()}>
          Refresh data
        </button>
      </div>

      <main className={`dashboard-grid${detail || detailLoading ? " with-detail" : ""}`}>
        <div className="main-column">
          {summary ? <CohortOverview summary={summary} /> : null}
          <RiskTable
            rows={rows}
            sortBy={sortBy}
            descending={descending}
            loading={loading}
            onSortChange={handleSortChange}
            onRowSelect={(row) => void handleRowSelect(row)}
            selectedBeneId={selectedBeneId}
          />
        </div>
        {detail || detailLoading ? (
          <BeneficiaryDetail detail={detail} loading={detailLoading} onClose={handleCloseDetail} />
        ) : null}
      </main>
    </div>
  );
}
