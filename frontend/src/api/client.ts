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
  QueryResult,
  RiskTargetShort,
  StudyEventType,
} from "../types";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
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
