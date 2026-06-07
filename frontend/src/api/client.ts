import type { ApiMeta, BeneficiaryDetail, BeneficiaryRow, CohortSummary } from "../types";

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
