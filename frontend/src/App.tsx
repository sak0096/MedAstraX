import { useCallback, useEffect, useState } from "react";
import {
  getBeneficiaries,
  getBeneficiaryDetail,
  getBeneficiaryExplanation,
  getCohortSummary,
  getGlobalImportance,
  getGroundedSummary,
  getMeta,
  getStudyMeta,
  getStudySession,
  exchangeLaunchToken,
} from "./api/client";
import { BeneficiaryDetail } from "./components/BeneficiaryDetail";
import { CohortFilterBar, type CohortFilterState } from "./components/CohortFilterBar";
import { CohortOverview } from "./components/CohortOverview";
import { ExportMenu } from "./components/ExportMenu";
import { GlobalImportancePanel } from "./components/GlobalImportancePanel";
import { ModelLimitationsPanel } from "./components/ModelLimitationsPanel";
import { QueryPanel } from "./components/QueryPanel";
import { RiskTable, type SortKey } from "./components/RiskTable";
import { StudyExportButton } from "./components/StudyExportButton";
import { TaskPanel } from "./components/TaskPanel";
import { CONDITION_COPY } from "./config/conditions";
import { getParticipantId, getSessionId, setActiveStudyTaskId, trackEvent, trackLatency } from "./instrumentation/logger";
import { getConditionFromUrl, getStudyArmFromUrl, isStudyModeFromUrl, takeLaunchCredential } from "./study/session";
import type {
  ApiMeta,
  BeneficiaryDetail as BeneficiaryDetailType,
  BeneficiaryExplanation,
  BeneficiaryRow,
  CohortSummary,
  GlobalImportance,
  GroundedSummary,
  QueryResult,
  RiskTargetShort,
  StudyCaseRef,
} from "./types";

const ROW_LIMIT = 250;
const DEFAULT_TARGETS: RiskTargetShort[] = [
  "hospitalization",
  "high_utilization",
  "elevated_cost",
];

export default function App() {
  const [meta, setMeta] = useState<ApiMeta | null>(null);
  const [priorityRuleDescription, setPriorityRuleDescription] = useState<string>("");
  const [studyAnalyticYear, setStudyAnalyticYear] = useState<number | null>(null);
  const [summary, setSummary] = useState<CohortSummary | null>(null);
  const [rows, setRows] = useState<BeneficiaryRow[]>([]);
  const [detail, setDetail] = useState<BeneficiaryDetailType | null>(null);
  const [explanation, setExplanation] = useState<BeneficiaryExplanation | null>(null);
  const [groundedSummary, setGroundedSummary] = useState<GroundedSummary | null>(null);
  const [globalImportance, setGlobalImportance] = useState<GlobalImportance | null>(null);
  const [globalTarget, setGlobalTarget] = useState<RiskTargetShort>("hospitalization");
  const [selectedBeneId, setSelectedBeneId] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [studyPhase, setStudyPhase] = useState<"initial" | "awaiting_ai" | "final" | "single" | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("hospitalization_risk");
  const [descending, setDescending] = useState(true);
  const [filters, setFilters] = useState<CohortFilterState>({
    chronicFilter: null,
    minTotalClaims: null,
  });
  const [lastQueryResult, setLastQueryResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [explanationUnavailable, setExplanationUnavailable] = useState(false);
  const [summaryUnavailable, setSummaryUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingLaunchToken, setPendingLaunchToken] = useState<string | null>(null);

  const condition = meta?.study_mode_enabled
    ? meta.experimental_condition
    : getConditionFromUrl() ?? meta?.experimental_condition ?? "baseline";
  const isXai = condition === "xai";
  const isLlm = condition === "llm";
  const copy = CONDITION_COPY[condition];
  const studyMode =
    Boolean(meta?.study_mode_enabled) &&
    (Boolean(meta?.assigned_study) || isStudyModeFromUrl());
  const studyArm = meta?.assigned_study ?? getStudyArmFromUrl();

  useEffect(() => {
    const parsed = takeLaunchCredential(window.location.search);
    if (!parsed.token) return;
    const nextUrl = `${window.location.pathname}${parsed.nextSearch}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
    setPendingLaunchToken(parsed.token);
  }, []);

  const continueFromLaunch = async () => {
    if (!pendingLaunchToken) return;
    try {
      await exchangeLaunchToken(pendingLaunchToken);
      setPendingLaunchToken(null);
      window.location.reload();
    } catch {
      setError("The study link could not be opened. Request a new link from the survey.");
    }
  };
  const showGlobalImportance = isXai && !studyMode;
  const allowSummary =
    isLlm && (activeTaskId !== "S2-T3" || studyPhase === "awaiting_ai" || studyPhase === "final");

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
        getBeneficiaries({
          limit: ROW_LIMIT,
          sort_by: sortBy,
          descending,
          chronic_filter: filters.chronicFilter,
          min_total_claims: filters.minTotalClaims,
          analytic_year: studyAnalyticYear,
        }),
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
  }, [sortBy, descending, filters.chronicFilter, filters.minTotalClaims, studyAnalyticYear]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (!studyMode) {
      setStudyAnalyticYear(null);
      return;
    }
    void getStudySession(getParticipantId())
      .then((session) => {
        setPriorityRuleDescription(String(session.priority_rule?.description ?? ""));
      })
      .catch(() => {
        setPriorityRuleDescription("");
      });
    void getStudyMeta()
      .then((studyMeta) => {
        if (typeof studyMeta.default_analytic_year === "number") {
          setStudyAnalyticYear(studyMeta.default_analytic_year);
        }
      })
      .catch(() => {
        setStudyAnalyticYear(2022);
      });
  }, [studyMode]);

  useEffect(() => {
    if (!allowSummary || !selectedBeneId || !detail || groundedSummary || !meta?.language_ready) {
      return;
    }
    let cancelled = false;
    setSummaryLoading(true);
    void getGroundedSummary(selectedBeneId, detail.analytic_year ?? undefined)
      .then((summaryResponse) => {
        if (!cancelled) {
          setGroundedSummary(summaryResponse);
          setSummaryUnavailable(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setGroundedSummary(null);
          setSummaryUnavailable(true);
        }
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [allowSummary, selectedBeneId, detail, groundedSummary, meta?.language_ready]);

  useEffect(() => {
    if (!meta?.instrumentation_enabled) return;
    const participant = getParticipantId();
    const loggedKey = `hc_session_logged:${participant}`;
    if (sessionStorage.getItem(loggedKey)) return;
    sessionStorage.setItem(loggedKey, "1");
    void trackEvent(
      "session_start",
      {
        participant_id: participant,
        session_id: getSessionId(),
        prototype_phase: meta.prototype_phase,
      },
      meta.experimental_condition,
    );
  }, [meta?.instrumentation_enabled, meta?.experimental_condition, meta?.prototype_phase]);

  const handleSortChange = (nextSortBy: SortKey) => {
    const nextDescending = nextSortBy === sortBy ? !descending : true;
    if (nextSortBy === sortBy) {
      setDescending(nextDescending);
    } else {
      setSortBy(nextSortBy);
      setDescending(true);
    }
    void trackEvent(
      "filter_change",
      { sort_by: nextSortBy, descending: nextDescending },
      condition,
    );
  };

  const handleFilterChange = (next: CohortFilterState) => {
    setFilters(next);
    void trackEvent(
      "filter_change",
      {
        chronic_filter: next.chronicFilter,
        min_total_claims: next.minTotalClaims,
      },
      condition,
    );
  };

  const handleGlobalTargetChange = (target: RiskTargetShort) => {
    setGlobalTarget(target);
    void loadGlobalImportance(target).catch((loadError) => {
      setError(
        loadError instanceof Error ? loadError.message : "Failed to load global importance.",
      );
    });
  };

  const handleQueryResults = (queryRows: BeneficiaryRow[], result: QueryResult) => {
    setRows(queryRows);
    setLastQueryResult(result);
    setSelectedBeneId(null);
    setDetail(null);
    setGroundedSummary(null);
    setExplanation(null);
  };

  const handleRowSelect = async (row: BeneficiaryRow) => {
    const started = performance.now();
    setSelectedBeneId(row.bene_id);
    setDetailLoading(true);
    void trackEvent(
      "drill_down",
      { bene_id: row.bene_id, analytic_year: row.analytic_year },
      condition,
    );
    setExplanation(null);
    setGroundedSummary(null);
    setExplanationUnavailable(false);
    setSummaryUnavailable(false);

    if (isXai && meta?.explanations_ready) {
      setExplanationLoading(true);
    }
    if (isLlm && meta?.language_ready && allowSummary) {
      setSummaryLoading(true);
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
          void trackEvent(
            "explanation_view",
            {
              bene_id: row.bene_id,
              analytic_year: row.analytic_year,
              contributor_count: explanationResponse.contributors.length,
            },
            condition,
          );
        } catch {
          setExplanation(null);
          setExplanationUnavailable(true);
        } finally {
          setExplanationLoading(false);
        }
      }

      if (isLlm && meta?.language_ready && allowSummary) {
        try {
          const summaryResponse = await getGroundedSummary(row.bene_id, row.analytic_year);
          setGroundedSummary(summaryResponse);
          setSummaryUnavailable(false);
        } catch {
          setGroundedSummary(null);
          setSummaryUnavailable(true);
        } finally {
          setSummaryLoading(false);
        }
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load beneficiary detail.");
    } finally {
      setDetailLoading(false);
      void trackLatency("drill_down", performance.now() - started, condition, {
        bene_id: row.bene_id,
      });
    }
  };

  const handleCloseDetail = () => {
    setSelectedBeneId(null);
    setDetail(null);
    setExplanation(null);
    setGroundedSummary(null);
    setExplanationUnavailable(false);
    setSummaryUnavailable(false);
  };

  const handleActiveTaskChange = (taskId: string | null) => {
    setActiveStudyTaskId(taskId);
    setActiveTaskId(taskId);
    if (!taskId) {
      setStudyPhase(null);
    }
  };

  const handleStudyPhaseChange = (phase: "initial" | "awaiting_ai" | "final" | "single" | null) => {
    setStudyPhase(phase);
  };

  const handleOpenStudyCase = (caseRef: StudyCaseRef) => {
    const row: BeneficiaryRow = {
      bene_id: caseRef.bene_id,
      analytic_year: Number(caseRef.analytic_year),
      age: null,
      sex: null,
      state_code: null,
      total_claims: null,
      total_payment_amt: null,
      chronic_condition_count: null,
      hospitalization_risk: null,
      high_utilization_risk: null,
      elevated_cost_risk: null,
    };
    void handleRowSelect(row);
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
          {!studyMode ? (
            <span className={`condition-badge ${condition}`}>{condition}</span>
          ) : (
            <span className="meta-pill">Study session</span>
          )}
          {!studyMode ? (
            <span className="meta-pill">Phase {meta?.prototype_phase ?? "8"}</span>
          ) : null}
          {meta?.predictions_ready ? (
            <span className="meta-pill ready">Data ready</span>
          ) : (
            <span className="meta-pill warn">Data missing</span>
          )}
          {!studyMode && (isXai || isLlm) ? (
            meta?.explanations_ready ? (
              <span className="meta-pill ready">Panels ready</span>
            ) : (
              <span className="meta-pill warn">Panels missing</span>
            )
          ) : null}
        </div>
      </header>

      {pendingLaunchToken ? (
        <div className="error-banner">
          <p>Continue to open your study session.</p>
          <button type="button" className="secondary-button" onClick={() => void continueFromLaunch()}>
            Continue
          </button>
        </div>
      ) : null}

      {error ? <div className="error-banner">{error}</div> : null}

      {isXai && meta && !meta.explanations_ready ? (
        <div className="error-banner">
          {studyMode
            ? "Some dashboard panels are temporarily unavailable. You can continue when they load, or use the closing questions if the session cannot continue."
            : (
              <>
                This dashboard version requires cached explanations. Run{" "}
                <code>python -m hc_analytics.explainability</code> then refresh.
              </>
            )}
        </div>
      ) : null}

      {isLlm && meta && !meta.language_ready ? (
        <div className="error-banner">
          {studyMode
            ? "Some dashboard panels are temporarily unavailable. You can continue when they load, or use the closing questions if the session cannot continue."
            : (
              <>
                This dashboard version requires evidence bundles. Run{" "}
                <code>python -m hc_analytics.explainability</code> then refresh.
              </>
            )}
        </div>
      ) : null}

      <div className="toolbar">
        {studyMode ? null : <ExportMenu rows={rows} summary={summary} condition={condition} />}
        {studyMode ? null : <StudyExportButton enabled={Boolean(meta?.instrumentation_enabled)} />}
        <button type="button" className="ghost-button" onClick={() => void loadDashboard()}>
          Refresh data
        </button>
      </div>

      {studyMode ? (
        <TaskPanel
          enabled={studyMode}
          studyArm={studyArm}
          condition={condition}
          onActiveTaskChange={handleActiveTaskChange}
          onStudyPhaseChange={handleStudyPhaseChange}
          onOpenCase={handleOpenStudyCase}
          lastQueryResult={lastQueryResult}
          summaryClaims={groundedSummary?.grounded.claims ?? []}
        />
      ) : null}

      {studyMode ? <ModelLimitationsPanel priorityRuleDescription={priorityRuleDescription} /> : null}

      <main className={`dashboard-grid${detail || detailLoading ? " with-detail" : ""}`}>
        <div className="main-column">
          {summary ? <CohortOverview summary={summary} /> : null}
          <CohortFilterBar filters={filters} onChange={handleFilterChange} />
          {isLlm ? <QueryPanel onResults={handleQueryResults} condition={condition} /> : null}
          {showGlobalImportance && globalImportance ? (
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
            groundedSummary={allowSummary ? groundedSummary : null}
            summaryLoading={allowSummary ? summaryLoading : false}
            summaryUnavailable={allowSummary ? summaryUnavailable : false}
            targets={DEFAULT_TARGETS}
          />
        ) : null}
      </main>
    </div>
  );
}
