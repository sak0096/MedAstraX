import { useEffect, useMemo, useState } from "react";
import {
  getStudySession,
  getStudyTasks,
  startStudyTask,
  submitStudyTaskResponse,
} from "../api/client";
import { getParticipantId, getSessionId, trackEvent } from "../instrumentation/logger";
import type { ExperimentalCondition, StudyCaseRef, StudyTaskDefinition } from "../types";

interface TaskPanelProps {
  enabled: boolean;
  studyArm: "study1" | "study2" | "full";
  condition: ExperimentalCondition;
  onActiveTaskChange: (taskId: string | null) => void;
  onOpenCase: (caseRef: StudyCaseRef) => void;
}

const STUDY1_TASKS = ["S1-T1", "S1-T2", "S1-T3", "S1-T4a", "S1-T4b", "S1-T5", "S1-T6"];
const STUDY2_TASKS = ["S2-T1", "S2-T2", "S2-T3", "S2-T4", "S2-T5", "S2-T6", "S2-T7"];

export function TaskPanel({
  enabled,
  studyArm,
  condition,
  onActiveTaskChange,
  onOpenCase,
}: TaskPanelProps) {
  const [tasks, setTasks] = useState<StudyTaskDefinition[]>([]);
  const [cases, setCases] = useState<StudyCaseRef[]>([]);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeManipulation, setActiveManipulation] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [responseText, setResponseText] = useState("");
  const [ranking, setRanking] = useState("");
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

  useEffect(() => {
    if (!enabled) return;
    const participantId = getParticipantId();
    void Promise.all([getStudySession(participantId), getStudyTasks()])
      .then(([session, taskPayload]) => {
        setCases(session.cases);
        setAssignments(session.assignments);
        const allowed = new Set(visibleTaskIds);
        setTasks(taskPayload.tasks.filter((task) => allowed.has(task.task_id)));
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "Failed to load study tasks.");
      });
  }, [enabled, visibleTaskIds]);

  const selectTask = async (taskId: string) => {
    setError(null);
    setStatus(null);
    setResponseText("");
    setRanking("");
    try {
      const started = await startStudyTask(taskId, getParticipantId(), getSessionId());
      setActiveTaskId(taskId);
      setActiveManipulation(started.active_manipulation);
      setStartedAt(Date.now());
      onActiveTaskChange(taskId);
      void trackEvent(
        "task_start",
        {
          task_id: taskId,
          active_manipulation: started.active_manipulation,
        },
        condition,
      );
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Failed to start task.");
    }
  };

  const completeTask = async () => {
    if (!activeTask) return;
    const responses: Record<string, unknown> = {};
    if (activeTask.response_type === "ranking") {
      responses.ranking = ranking
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    } else {
      responses.text = responseText.trim();
    }

    try {
      await submitStudyTaskResponse(activeTask.task_id, {
        participant_id: getParticipantId(),
        session_id: getSessionId(),
        responses,
        time_ms: startedAt ? Date.now() - startedAt : undefined,
      });
      void trackEvent(
        "task_response",
        {
          task_id: activeTask.task_id,
          response_type: activeTask.response_type,
          active_manipulation: activeManipulation,
        },
        condition,
      );
      setStatus(`Saved response for ${activeTask.task_id}.`);
      setActiveTaskId(null);
      setActiveManipulation(null);
      setStartedAt(null);
      onActiveTaskChange(null);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to save response.");
    }
  };

  if (!enabled) return null;

  return (
    <section className={`panel study-panel${collapsed ? " collapsed" : ""}`}>
      <div className="panel-header">
        <div>
          <h2>Study Tasks</h2>
          <p className="panel-subtitle">
            Guided protocol for {studyArm === "full" ? "Studies 1 & 2" : studyArm}. Active task
            headers enable manipulation trials for assigned cases.
          </p>
        </div>
        <button type="button" className="ghost-button" onClick={() => setCollapsed((value) => !value)}>
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>

      {!collapsed ? (
        <>
          <div className="study-assignments">
            <span>Study 1 manipulation: {assignments.study1 ?? "—"}</span>
            <span>Study 2 manipulation: {assignments.study2 ?? "—"}</span>
          </div>

          {error ? <p className="query-error">{error}</p> : null}
          {status ? <p className="study-export-status">{status}</p> : null}

          <div className="study-task-list">
            {filteredTasks.map((task) => (
              <button
                key={task.task_id}
                type="button"
                className={`study-task-button${activeTaskId === task.task_id ? " active" : ""}`}
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
              {activeManipulation ? (
                <p className="study-manipulation-note">
                  Active manipulation for this task: <strong>{activeManipulation}</strong>
                </p>
              ) : null}
              {activeTask.suggested_query ? (
                <p className="panel-subtitle">Suggested query: “{activeTask.suggested_query}”</p>
              ) : null}

              {activeTask.requires_cases.length > 0 ? (
                <div className="study-case-actions">
                  {activeTask.requires_cases.map((caseId) => {
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
                  })}
                </div>
              ) : null}

              {activeTask.response_type === "ranking" ? (
                <label className="study-response-field">
                  <span>Outreach ranking (comma-separated case IDs, e.g. B-01, B-03, B-02, B-04)</span>
                  <input
                    type="text"
                    value={ranking}
                    onChange={(event) => setRanking(event.target.value)}
                    placeholder="B-01, B-02, B-03, B-04"
                  />
                </label>
              ) : activeTask.response_type !== "completion" && activeTask.response_type !== "query_flow" ? (
                <label className="study-response-field">
                  <span>Task response</span>
                  <textarea
                    rows={4}
                    value={responseText}
                    onChange={(event) => setResponseText(event.target.value)}
                    placeholder="Enter your answer or notes for this task."
                  />
                </label>
              ) : (
                <p className="panel-subtitle">
                  Complete the task in the dashboard interface, then mark complete when done.
                </p>
              )}

              <div className="query-actions">
                <button type="button" className="secondary-button" onClick={() => void completeTask()}>
                  Mark task complete
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => {
                    setActiveTaskId(null);
                    setActiveManipulation(null);
                    setStartedAt(null);
                    onActiveTaskChange(null);
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
