import { useEffect, useMemo, useState } from "react";
import {
  getOutreachRecommendation,
  getStudySession,
  getStudyTasks,
  startStudyTask,
  submitStudyTaskResponse,
} from "../api/client";
import { getParticipantId, getSessionId, trackEvent } from "../instrumentation/logger";
import {
  hasPassedComprehension,
  isFacilitatorModeFromUrl,
} from "../study/session";
import type {
  ComprehensionQuestion,
  ExperimentalCondition,
  OutreachRecommendation,
  QueryResult,
  StudyCaseRef,
  StudyTaskDefinition,
} from "../types";
import { FEATURE_LABELS } from "../utils/xai";
import { ComprehensionGate } from "./ComprehensionGate";
import { OutreachRecommendationPanel } from "./OutreachRecommendationPanel";
import { RankingEditor } from "./RankingEditor";

interface TaskPanelProps {
  enabled: boolean;
  studyArm: "study1" | "study2" | "full";
  condition: ExperimentalCondition;
  onActiveTaskChange: (taskId: string | null) => void;
  onStudyPhaseChange?: (phase: "initial" | "awaiting_ai" | "final" | "single" | null) => void;
  onOpenCase: (caseRef: StudyCaseRef) => void;
  lastQueryResult?: QueryResult | null;
}

const STUDY1_TASKS = ["S1-T0", "S1-T1", "S1-T2", "S1-T3", "S1-T4a", "S1-T4b", "S1-T5", "S1-T6"];
const STUDY2_TASKS = ["S2-T0", "S2-T1", "S2-T2", "S2-T3", "S2-T4", "S2-T5", "S2-T6", "S2-T7"];
const DRIVER_FEATURES = Object.keys(FEATURE_LABELS);
const EMPTY_DRIVERS = [
  { feature: "", direction: "increases_risk" },
  { feature: "", direction: "increases_risk" },
  { feature: "", direction: "increases_risk" },
];

const CONFIDENCE_OPTIONS = [1, 2, 3, 4, 5, 6, 7];
const RELIANCE_OPTIONS = [
  { value: "priority_rule", label: "Operational priority rule" },
  { value: "risk_scores", label: "Risk scores" },
  { value: "explanations", label: "Explanations / summary" },
  { value: "own_judgment", label: "Own judgment" },
];

export function TaskPanel({
  enabled,
  studyArm,
  condition,
  onActiveTaskChange,
  onStudyPhaseChange,
  onOpenCase,
  lastQueryResult = null,
}: TaskPanelProps) {
  const facilitatorMode = isFacilitatorModeFromUrl();
  const [tasks, setTasks] = useState<StudyTaskDefinition[]>([]);
  const [cases, setCases] = useState<StudyCaseRef[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [priorityRuleDescription, setPriorityRuleDescription] = useState<string>("");
  const [comprehensionQuestions, setComprehensionQuestions] = useState<ComprehensionQuestion[]>([]);
  const [comprehensionThreshold, setComprehensionThreshold] = useState(2);
  const [comprehensionPassed, setComprehensionPassed] = useState(hasPassedComprehension(studyArm));
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeManipulation, setActiveManipulation] = useState<string | null>(null);
  const [trialId, setTrialId] = useState<string | null>(null);
  const [outreachCaseIds, setOutreachCaseIds] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [phase, setPhase] = useState<"initial" | "awaiting_ai" | "final" | "single">("single");
  const [responseText, setResponseText] = useState("");
  const [ranking, setRanking] = useState<string[]>([]);
  const [drivers, setDrivers] = useState(EMPTY_DRIVERS);
  const [beneficiaryIds, setBeneficiaryIds] = useState(["", "", "", "", ""]);
  const [resultCount, setResultCount] = useState("");
  const [topBeneId, setTopBeneId] = useState("");
  const [confidence, setConfidence] = useState<number>(4);
  const [relianceSource, setRelianceSource] = useState("priority_rule");
  const [claimSupported, setClaimSupported] = useState<"supported" | "unsupported" | "">("");
  const [flaggedClaim, setFlaggedClaim] = useState("");
  const [recommendation, setRecommendation] = useState<OutreachRecommendation | null>(null);
  const [recommendationLoading, setRecommendationLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  const visibleTaskIds = useMemo(() => {
    if (studyArm === "study1") return STUDY1_TASKS;
    if (studyArm === "study2") return STUDY2_TASKS;
    return [...STUDY1_TASKS, ...STUDY2_TASKS];
  }, [studyArm]);

  const activeTask = tasks.find((task) => task.task_id === activeTaskId) ?? null;

  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      if (!visibleTaskIds.includes(task.task_id)) return false;
      if (task.conditions.length === 0) return true;
      return task.conditions.includes(condition);
    });
  }, [tasks, visibleTaskIds, condition]);

  const outreachCases = useMemo(() => {
    const ids = new Set(outreachCaseIds);
    return cases.filter((caseRef) => ids.has(caseRef.case_id));
  }, [cases, outreachCaseIds]);

  useEffect(() => {
    if (!enabled) return;
    const participantId = getParticipantId();
    void Promise.all([getStudySession(participantId), getStudyTasks()])
      .then(([session, taskPayload]) => {
        setCases(session.cases);
        setAssignments(session.assignments);
        setPriorityRuleDescription(String(session.priority_rule?.description ?? ""));
        const comprehension =
          studyArm === "study2"
            ? (session.comprehension_study2 ?? session.comprehension ?? {})
            : (session.comprehension ?? {});
        setComprehensionQuestions((comprehension.questions as ComprehensionQuestion[]) ?? []);
        setComprehensionThreshold(Number(comprehension.pass_threshold ?? 2));
        const allowed = new Set(visibleTaskIds);
        setTasks(taskPayload.tasks.filter((task) => allowed.has(task.task_id)));
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "Failed to load study tasks.");
      });
  }, [enabled, visibleTaskIds]);

  const resetResponseFields = () => {
    setResponseText("");
    setRanking([]);
    setDrivers(EMPTY_DRIVERS);
    setBeneficiaryIds(["", "", "", "", ""]);
    setResultCount("");
    setTopBeneId("");
    setConfidence(4);
    setRelianceSource("priority_rule");
    setClaimSupported("");
    setFlaggedClaim("");
    setRecommendation(null);
    setPhase("single");
  };

  const selectTask = async (taskId: string) => {
    setError(null);
    setStatus(null);
    resetResponseFields();
    try {
      const started = await startStudyTask(taskId, getParticipantId(), getSessionId());
      setActiveTaskId(taskId);
      setActiveManipulation(started.active_manipulation);
      setTrialId(started.trial_id);
      setOutreachCaseIds(started.outreach_case_ids ?? []);
      setRanking(started.outreach_case_ids ?? []);
      setStartedAt(Date.now());
      onActiveTaskChange(taskId);
      const nextPhase = started.task.sequential_judgment ? "initial" : "single";
      setPhase(nextPhase);
      onStudyPhaseChange?.(nextPhase);
      void trackEvent(
      "task_start",
      {
        task_id: taskId,
        trial_id: started.trial_id,
      },
      condition,
    );
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Failed to start task.");
    }
  };

  const buildResponses = () => {
    if (activeTask?.response_type === "sequential_ranking" || activeTask?.response_type === "ranking") {
      return { ranking };
    }
    if (activeTask?.response_type === "feature_list") {
      return { drivers };
    }
    if (activeTask?.response_type === "cohort_selection" || activeTask?.response_type === "beneficiary_list") {
      const ids = beneficiaryIds.map((item) => item.trim()).filter(Boolean);
      return {
        result_count: resultCount === "" ? null : Number(resultCount),
        top_bene_id: topBeneId.trim() || null,
        result_ids: ids,
        beneficiary_ids: ids,
      };
    }
    if (activeTask?.response_type === "query_flow") {
      const ids = (lastQueryResult?.rows ?? []).map((row) => row.bene_id);
      return {
        query_id: lastQueryResult?.query_id ?? null,
        result_ids: ids,
        result_count: lastQueryResult?.row_count ?? null,
        top_bene_id: ids[0] ?? null,
        parameters: lastQueryResult?.parameters ?? null,
      };
    }
    if (activeTask?.response_type === "sequential_claim_review") {
      return {
        supported: claimSupported,
        flagged_claim: flaggedClaim.trim() || null,
        notes: responseText.trim() || null,
      };
    }
    return { text: responseText.trim() };
  };

  const submitPhase = async (submitPhase: "initial" | "final" | "single") => {
    if (!activeTask) return;
    try {
      await submitStudyTaskResponse(activeTask.task_id, {
        participant_id: getParticipantId(),
        session_id: getSessionId(),
        trial_id: trialId ?? undefined,
        phase: submitPhase,
        responses: buildResponses(),
        confidence,
        reliance_source: relianceSource,
        time_ms: startedAt ? Date.now() - startedAt : undefined,
      });
      // Canonical task events are written by the study API; do not emit a sparse duplicate.

      if (submitPhase === "initial") {
        setStatus("Initial response saved. Review AI assistance, then submit your final judgment.");
        setPhase("awaiting_ai");
        onStudyPhaseChange?.("awaiting_ai");
        return;
      }

      setStatus(`Saved ${submitPhase} response for ${activeTask.task_id}.`);
      setActiveTaskId(null);
      setActiveManipulation(null);
      setTrialId(null);
      setStartedAt(null);
      resetResponseFields();
      onActiveTaskChange(null);
      onStudyPhaseChange?.(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to save response.");
    }
  };

  const loadRecommendation = async () => {
    if (!activeTask) return;
    setRecommendationLoading(true);
    setError(null);
    try {
      const payload = await getOutreachRecommendation(activeTask.task_id, getParticipantId());
      setRecommendation(payload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load recommendation.");
    } finally {
      setRecommendationLoading(false);
    }
  };

  const renderResponseFields = () => {
    if (!activeTask) return null;

    if (activeTask.response_type === "comprehension") {
      return (
        <ComprehensionGate
          questions={comprehensionQuestions}
          passThreshold={comprehensionThreshold}
          attemptKey={studyArm}
          study={studyArm === "study2" ? "study2" : "study1"}
          onPassed={() => {
            setComprehensionPassed(true);
            setStatus("Comprehension check passed. Continue with the next task.");
          }}
        />
      );
    }

    const isRanking =
      activeTask.response_type === "sequential_ranking" || activeTask.response_type === "ranking";
    const isClaimReview = activeTask.response_type === "sequential_claim_review";

    return (
      <>
        {isRanking ? (
          <RankingEditor caseIds={outreachCaseIds} value={ranking} onChange={setRanking} />
        ) : null}

        {isClaimReview ? (
          <>
            <label className="study-response-field">
              <span>Is the summary supported by the record?</span>
              <select
                value={claimSupported}
                onChange={(event) => setClaimSupported(event.target.value as "supported" | "unsupported")}
              >
                <option value="">Select…</option>
                <option value="supported">Supported</option>
                <option value="unsupported">Contains unsupported claim(s)</option>
              </select>
            </label>
            <label className="study-response-field">
              <span>Flagged claim (if any)</span>
              <input
                type="text"
                value={flaggedClaim}
                onChange={(event) => setFlaggedClaim(event.target.value)}
                placeholder="Paste or describe the unsupported claim"
              />
            </label>
          </>
        ) : null}

        {activeTask.response_type === "feature_list" ? (
          <div className="driver-form">
            {drivers.map((driver, index) => (
              <div key={`driver-${index}`} className="filter-controls">
                <label className="study-response-field">
                  <span>Driver {index + 1}</span>
                  <select
                    value={driver.feature}
                    onChange={(event) =>
                      setDrivers((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, feature: event.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="">Select feature</option>
                    {DRIVER_FEATURES.map((feature) => (
                      <option key={feature} value={feature}>
                        {FEATURE_LABELS[feature] ?? feature}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="study-response-field">
                  <span>Direction</span>
                  <select
                    value={driver.direction}
                    onChange={(event) =>
                      setDrivers((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, direction: event.target.value } : item,
                        ),
                      )
                    }
                  >
                    <option value="increases_risk">Increases risk</option>
                    <option value="decreases_risk">Decreases risk</option>
                  </select>
                </label>
              </div>
            ))}
          </div>
        ) : null}

        {activeTask.response_type === "cohort_selection" || activeTask.response_type === "beneficiary_list" ? (
          <div className="driver-form">
            <label className="study-response-field">
              <span>Result count</span>
              <input
                type="number"
                min={0}
                value={resultCount}
                onChange={(event) => setResultCount(event.target.value)}
              />
            </label>
            <label className="study-response-field">
              <span>Highest-risk beneficiary ID</span>
              <input type="text" value={topBeneId} onChange={(event) => setTopBeneId(event.target.value)} />
            </label>
            {beneficiaryIds.map((value, index) => (
              <label key={`bene-${index}`} className="study-response-field">
                <span>Optional ID {index + 1}</span>
                <input
                  type="text"
                  value={value}
                  onChange={(event) =>
                    setBeneficiaryIds((current) =>
                      current.map((item, itemIndex) => (itemIndex === index ? event.target.value : item)),
                    )
                  }
                />
              </label>
            ))}
          </div>
        ) : null}

        {activeTask.response_type === "query_flow" ? (
          <p className="panel-subtitle">
            {lastQueryResult
              ? `Captured count ${lastQueryResult.row_count} and top ID ${lastQueryResult.rows[0]?.bene_id ?? "—"}. Mark complete when finished.`
              : "Complete the search in the dashboard, then mark complete."}
          </p>
        ) : null}

        {!isRanking &&
        !isClaimReview &&
        activeTask.response_type !== "completion" &&
        activeTask.response_type !== "query_flow" &&
        activeTask.response_type !== "feature_list" &&
        activeTask.response_type !== "beneficiary_list" &&
        activeTask.response_type !== "cohort_selection" ? (
          <label className="study-response-field">
            <span>Task response</span>
            <textarea
              rows={4}
              value={responseText}
              onChange={(event) => setResponseText(event.target.value)}
              placeholder="Enter your answer or notes for this task."
            />
          </label>
        ) : null}

        {activeTask.response_type === "completion" ? (
          <p className="panel-subtitle">Complete the task in the dashboard interface, then mark complete.</p>
        ) : null}

        {phase !== "single" || isRanking || isClaimReview ? (
          <>
            <label className="study-response-field">
              <span>Confidence (1 = low, 7 = high)</span>
              <select value={confidence} onChange={(event) => setConfidence(Number(event.target.value))}>
                {CONFIDENCE_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="study-response-field">
              <span>Primary reliance source</span>
              <select value={relianceSource} onChange={(event) => setRelianceSource(event.target.value)}>
                {RELIANCE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        ) : null}

        {phase === "awaiting_ai" && isRanking ? (
          <>
            <OutreachRecommendationPanel recommendation={recommendation} loading={recommendationLoading} />
            <div className="query-actions">
              <button type="button" className="secondary-button" onClick={() => void loadRecommendation()}>
                Show AI recommendation
              </button>
              <button type="button" className="secondary-button" onClick={() => {
                setPhase("final");
                onStudyPhaseChange?.("final");
              }}>
                Enter final ranking
              </button>
            </div>
          </>
        ) : null}

        {phase === "final" && isRanking ? (
          <div className="query-actions">
            <button type="button" className="secondary-button" onClick={() => void submitPhase("final")}>
              Submit final ranking
            </button>
          </div>
        ) : null}

        {phase === "initial" && (isRanking || isClaimReview) ? (
          <div className="query-actions">
            <button type="button" className="secondary-button" onClick={() => void submitPhase("initial")}>
              Submit initial judgment
            </button>
          </div>
        ) : null}

        {phase === "awaiting_ai" && isClaimReview ? (
          <div className="query-actions">
            <button type="button" className="secondary-button" onClick={() => {
              setPhase("final");
              onStudyPhaseChange?.("final");
            }}>
              Review summary and enter final judgment
            </button>
          </div>
        ) : null}

        {phase === "final" && isClaimReview ? (
          <div className="query-actions">
            <button type="button" className="secondary-button" onClick={() => void submitPhase("final")}>
              Submit final judgment
            </button>
          </div>
        ) : null}

        {phase === "single" && activeTask.response_type !== "comprehension" ? (
          <div className="query-actions">
            <button type="button" className="secondary-button" onClick={() => void submitPhase("single")}>
              Mark task complete
            </button>
          </div>
        ) : null}
      </>
    );
  };

  if (!enabled) return null;

  const studyBlocked =
    (studyArm === "study1" || studyArm === "study2") && !comprehensionPassed;

  return (
    <section className={`panel study-panel${collapsed ? " collapsed" : ""}`}>
      <div className="panel-header">
        <div>
          <h2>Study Tasks</h2>
          <p className="panel-subtitle">
            Guided protocol for {studyArm === "full" ? "Studies 1 & 2 (facilitator/dev only)" : studyArm}.
          </p>
          {studyArm === "full" ? (
            <p className="study-warning">
              Use <code>?study=study1</code> or <code>?study=study2</code> for participant sessions.
            </p>
          ) : null}
        </div>
        <button type="button" className="ghost-button" onClick={() => setCollapsed((value) => !value)}>
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>

      {!collapsed ? (
        <>
          {facilitatorMode ? (
            <div className="study-assignments facilitator-only">
              <span>S1-T5: {assignments["S1-T5"] ?? assignments.study1 ?? "—"}</span>
              <span>S2-T2: {assignments["S2-T2"] ?? "—"}</span>
              <span>S2-T3: {assignments["S2-T3"] ?? "—"}</span>
              <span>S2-T6: {assignments["S2-T6"] ?? "—"}</span>
            </div>
          ) : null}

          {error ? <p className="query-error">{error}</p> : null}
          {status ? <p className="study-export-status">{status}</p> : null}
          {priorityRuleDescription ? (
            <p className="panel-subtitle priority-inline">{priorityRuleDescription}</p>
          ) : null}

          <div className="study-task-list">
            {filteredTasks.map((task) => (
              <button
                key={task.task_id}
                type="button"
                className={`study-task-button${activeTaskId === task.task_id ? " active" : ""}`}
                disabled={studyBlocked && task.task_id !== "S1-T0" && task.task_id !== "S2-T0"}
                onClick={() => void selectTask(task.task_id)}
              >
                <strong>{task.task_id}</strong>
                <span>{task.title}</span>
                <span>{task.time_limit_min} min</span>
              </button>
            ))}
          </div>

          {activeTask ? (
            <div className="study-active-task">
              <h3>
                {activeTask.task_id}: {activeTask.title}
              </h3>
              <p>{activeTask.instructions}</p>
              {facilitatorMode && activeManipulation ? (
                <p className="study-manipulation-note facilitator-only">
                  Facilitator note — active manipulation: <strong>{activeManipulation}</strong>
                </p>
              ) : null}
              {activeTask.suggested_query ? (
                <p className="panel-subtitle">Suggested query: “{activeTask.suggested_query}”</p>
              ) : null}

              {(activeTask.requires_cases.length > 0 ? activeTask.requires_cases : outreachCaseIds).length > 0 ? (
                <div className="study-case-actions">
                  {(activeTask.requires_cases.length > 0 ? activeTask.requires_cases : outreachCaseIds).map(
                    (caseId) => {
                      const caseRef = cases.find((item) => item.case_id === caseId);
                      if (!caseRef) return null;
                      return (
                        <button
                          key={caseId}
                          type="button"
                          className="secondary-button"
                          onClick={() => onOpenCase(caseRef)}
                        >
                          Open {caseRef.label}
                        </button>
                      );
                    },
                  )}
                </div>
              ) : null}

              {outreachCases.length > 0 && activeTask.response_type === "sequential_ranking" ? (
                <div className="study-case-actions">
                  {outreachCases.map((caseRef) => (
                    <button
                      key={caseRef.case_id}
                      type="button"
                      className="secondary-button"
                      onClick={() => onOpenCase(caseRef)}
                    >
                      Open {caseRef.label}
                    </button>
                  ))}
                </div>
              ) : null}

              {renderResponseFields()}

              <div className="query-actions">
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => {
                    setActiveTaskId(null);
                    setActiveManipulation(null);
                    setTrialId(null);
                    setStartedAt(null);
                    resetResponseFields();
                    onActiveTaskChange(null);
                    onStudyPhaseChange?.(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
