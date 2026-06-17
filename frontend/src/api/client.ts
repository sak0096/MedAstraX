import type {
  ApiMeta,
  BeneficiaryDetail,
  BeneficiaryExplanation,
  BeneficiaryRow,
  CohortSummary,
  ExplanationsMeta,
  ExperimentalCondition,
  GlobalImportance,
  GroundedSummary,
  InterpretedQuery,
  OutreachRecommendation,
  QueryResult,
  RiskTargetShort,
  StudyEventType,
  StudySession,
  StudyTaskDefinition,
} from "../types";
import { getActiveStudyTaskId } from "../study/session";
import { getParticipantId, getSessionId } from "../instrumentation/logger";

function studyHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Participant-Id": getParticipantId(),
    "X-Study-Session-Id": getSessionId(),
  };
  const taskId = getActiveStudyTaskId();
  if (taskId) {
    headers["X-Study-Task-Id"] = taskId;
  }
  return headers;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...studyHeaders(),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getMeta(): Promise<ApiMeta> {
  return fetchJson<ApiMeta>("/api/meta");
}

export function getCohortSummary(): Promise<CohortSummary> {
  return fetchJson<CohortSummary>("/api/cohort/summary");
}

export function getBeneficiaries(params: {
  limit?: number;
  sort_by?: string;
  descending?: boolean;
}): Promise<{ count: number; sort_by: string; rows: BeneficiaryRow[] }> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.sort_by) search.set("sort_by", params.sort_by);
  if (params.descending !== undefined) {
    search.set("descending", String(params.descending));
  }
  const query = search.toString();
  return fetchJson(`/api/beneficiaries${query ? `?${query}` : ""}`);
}

export function getBeneficiaryDetail(
  beneId: string,
  analyticYear?: number,
): Promise<BeneficiaryDetail> {
  const search = new URLSearchParams();
  if (analyticYear !== undefined) {
    search.set("analytic_year", String(analyticYear));
  }
  const query = search.toString();
  return fetchJson(`/api/beneficiaries/${encodeURIComponent(beneId)}${query ? `?${query}` : ""}`);
}

export function getExplanationsMeta(): Promise<ExplanationsMeta> {
  return fetchJson<ExplanationsMeta>("/api/explanations/meta");
}

export function getGlobalImportance(target: RiskTargetShort): Promise<GlobalImportance> {
  return fetchJson<GlobalImportance>(`/api/explanations/global?target=${target}`);
}

export function getBeneficiaryExplanation(
  beneId: string,
  analyticYear: number,
  topK = 5,
): Promise<BeneficiaryExplanation> {
  const search = new URLSearchParams({
    analytic_year: String(analyticYear),
    top_k: String(topK),
  });
  return fetchJson(
    `/api/explanations/${encodeURIComponent(beneId)}?${search.toString()}`,
  );
}

export function getGroundedSummary(
  beneId: string,
  analyticYear?: number,
): Promise<GroundedSummary> {
  const search = new URLSearchParams();
  if (analyticYear !== undefined) {
    search.set("analytic_year", String(analyticYear));
  }
  const query = search.toString();
  return fetchJson(
    `/api/language/summary/${encodeURIComponent(beneId)}${query ? `?${query}` : ""}`,
  );
}

export function interpretQuery(query: string): Promise<InterpretedQuery> {
  return fetchJson<InterpretedQuery>("/api/language/query/interpret", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export function executeQuery(queryId: string): Promise<QueryResult> {
  return fetchJson<QueryResult>("/api/language/query/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query_id: queryId, confirmed: true }),
  });
}

export function postStudyEvent(event: {
  event_type: StudyEventType;
  session_id: string;
  participant_id: string;
  condition?: ExperimentalCondition;
  task_id?: string;
  payload?: Record<string, unknown>;
}): Promise<{ stored: boolean }> {
  return fetchJson("/api/instrumentation/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(event),
  });
}

export function exportStudySession(sessionId: string): Promise<{
  session_id: string;
  export_path: string;
  event_count: number;
}> {
  return fetchJson("/api/instrumentation/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export function getStudySession(participantId: string): Promise<StudySession> {
  return fetchJson(`/api/study/session?participant_id=${encodeURIComponent(participantId)}`);
}

export function getStudyTasks(study?: "study1" | "study2"): Promise<{ tasks: StudyTaskDefinition[] }> {
  const query = study ? `?study=${study}` : "";
  return fetchJson(`/api/study/tasks${query}`);
}

export function startStudyTask(
  taskId: string,
  participantId: string,
  sessionId: string,
): Promise<{
  task: StudyTaskDefinition;
  active_manipulation: string | null;
  trial_id: string | null;
  outreach_case_ids: string[];
  cases: StudySession["cases"];
}> {
  const search = new URLSearchParams({
    participant_id: participantId,
    session_id: sessionId,
  });
  return fetchJson(`/api/study/tasks/${encodeURIComponent(taskId)}/start?${search.toString()}`, {
    method: "POST",
  });
}

export function submitStudyTaskResponse(
  taskId: string,
  submission: {
    participant_id: string;
    session_id: string;
    trial_id?: string;
    phase?: "initial" | "final" | "single";
    responses: Record<string, unknown>;
    confidence?: number;
    reliance_source?: string;
    time_ms?: number;
    notes?: string;
  },
): Promise<{ stored: boolean; task_id: string; phase?: string }> {
  return fetchJson(`/api/study/tasks/${encodeURIComponent(taskId)}/response`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(submission),
  });
}

export function getOutreachRecommendation(
  taskId: string,
  participantId: string,
): Promise<OutreachRecommendation> {
  const search = new URLSearchParams({ participant_id: participantId });
  return fetchJson(
    `/api/study/tasks/${encodeURIComponent(taskId)}/recommendation?${search.toString()}`,
  );
}

export function submitComprehension(submission: {
  participant_id: string;
  session_id: string;
  answers: Record<string, number>;
}): Promise<{
  passed: boolean;
  correct: number;
  total: number;
  results: Array<{ question_id: string; correct: boolean }>;
}> {
  return fetchJson("/api/study/comprehension", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(submission),
  });
}
