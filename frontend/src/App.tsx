import { useCallback, useEffect, useState } from "react";
import {
  getBeneficiaries,
  getBeneficiaryDetail,
  getBeneficiaryExplanation,
  getCohortSummary,
  getGlobalImportance,
  getMeta,
} from "./api/client";
import { BeneficiaryDetail } from "./components/BeneficiaryDetail";
import { CohortOverview } from "./components/CohortOverview";
import { ExportMenu } from "./components/ExportMenu";
import { GlobalImportancePanel } from "./components/GlobalImportancePanel";
import { RiskTable, type SortKey } from "./components/RiskTable";
import { CONDITION_COPY } from "./config/conditions";
import type {
  ApiMeta,
  BeneficiaryDetail as BeneficiaryDetailType,
  BeneficiaryExplanation,
  BeneficiaryRow,
  CohortSummary,
  GlobalImportance,
  RiskTargetShort,
} from "./types";

const ROW_LIMIT = 250;
const DEFAULT_TARGETS: RiskTargetShort[] = [
  "hospitalization",
  "high_utilization",
  "elevated_cost",
];

export default function App() {
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const [summary, setSummary] = useState<CohortSummary | null>(null);
  const [rows, setRows] = useState<BeneficiaryRow[]>([]);
  const [detail, setDetail] = useState<BeneficiaryDetailType | null>(null);
  const [explanation, setExplanation] = useState<BeneficiaryExplanation | null>(null);
  const [globalImportance, setGlobalImportance] = useState<GlobalImportance | null>(null);
  const [globalTarget, setGlobalTarget] = useState<RiskTargetShort>("hospitalization");
  const [selectedBeneId, setSelectedBeneId] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("hospitalization_risk");
  const [descending, setDescending] = useState(true);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationUnavailable, setExplanationUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const condition = meta?.experimental_condition ?? "baseline";
  const isXai = condition === "xai";
  const copy = CONDITION_COPY[condition];

  const loadGlobalImportance = useCallback(
    async (target: RiskTargetShort) => {
      if (!isXai || !meta?.explanations_ready) return;
      const response = await getGlobalImportance(target);
      setGlobalImportance(response);
    },
    [isXai, meta?.explanations_ready],
  );

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

      if (metaResponse.experimental_condition === "xai" && metaResponse.explanations_ready) {
        const globalResponse = await getGlobalImportance("hospitalization");
        setGlobalImportance(globalResponse);
        setGlobalTarget("hospitalization");
      } else {
        setGlobalImportance(null);
      }
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

  const handleGlobalTargetChange = (target: RiskTargetShort) => {
    setGlobalTarget(target);
    void loadGlobalImportance(target).catch((loadError) => {
      setError(
        loadError instanceof Error ? loadError.message : "Failed to load global importance.",
      );
    });
  };

  const handleRowSelect = async (row: BeneficiaryRow) => {
    setSelectedBeneId(row.bene_id);
    setDetailLoading(true);
    setExplanation(null);
    setExplanationUnavailable(false);

    if (isXai && meta?.explanations_ready) {
      setExplanationLoading(true);
    }

    try {
      const detailResponse = await getBeneficiaryDetail(row.bene_id, row.analytic_year);
      setDetail(detailResponse);

      if (isXai && meta?.explanations_ready) {
        try {
          const explanationResponse = await getBeneficiaryExplanation(
            row.bene_id,
            row.analytic_year,
            5,
          );
          setExplanation(explanationResponse);
          setExplanationUnavailable(false);
        } catch {
          setExplanation(null);
          setExplanationUnavailable(true);
        } finally {
          setExplanationLoading(false);
        }
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load beneficiary detail.");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedBeneId(null);
    setDetail(null);
    setExplanation(null);
    setExplanationUnavailable(false);
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">MedAstraX Research Prototype</p>
          <h1>{copy.title}</h1>
          <p className="header-copy">{copy.subtitle}</p>
        </div>
        <div className="header-meta">
          <span className={`condition-badge ${condition}`}>{condition}</span>
          <span className="meta-pill">Phase {meta?.prototype_phase ?? "6"}</span>
          {meta?.predictions_ready ? (
            <span className="meta-pill ready">Predictions ready</span>
          ) : (
            <span className="meta-pill warn">Predictions missing</span>
          )}
          {isXai ? (
            meta?.explanations_ready ? (
              <span className="meta-pill ready">Explanations ready</span>
            ) : (
              <span className="meta-pill warn">Explanations missing</span>
            )
          ) : null}
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      {isXai && meta && !meta.explanations_ready ? (
        <div className="error-banner">
          XAI condition requires cached explanations. Run{" "}
          <code>python -m hc_analytics.explainability</code> then refresh.
        </div>
      ) : null}

      <div className="toolbar">
        <ExportMenu rows={rows} summary={summary} />
        <button type="button" className="ghost-button" onClick={() => void loadDashboard()}>
          Refresh data
        </button>
      </div>

      <main className={`dashboard-grid${detail || detailLoading ? " with-detail" : ""}`}>
        <div className="main-column">
          {summary ? <CohortOverview summary={summary} /> : null}
          {isXai && globalImportance ? (
            <GlobalImportancePanel
              importance={globalImportance}
              selectedTarget={globalTarget}
              onTargetChange={handleGlobalTargetChange}
              targets={DEFAULT_TARGETS}
            />
          ) : null}
          <RiskTable
            rows={rows}
            sortBy={sortBy}
            descending={descending}
            loading={loading}
            onSortChange={handleSortChange}
            onRowSelect={(row) => void handleRowSelect(row)}
            selectedBeneId={selectedBeneId}
            condition={condition}
          />
        </div>
        {detail || detailLoading ? (
          <BeneficiaryDetail
            detail={detail}
            loading={detailLoading}
            onClose={handleCloseDetail}
            condition={condition}
            explanation={explanation}
            explanationLoading={explanationLoading}
            explanationUnavailable={explanationUnavailable}
            targets={DEFAULT_TARGETS}
          />
        ) : null}
      </main>
    </div>
  );
}
