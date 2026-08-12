import { postStudyEvent } from "../api/client";
import type { ExperimentalCondition } from "../types";
import { setActiveStudyTaskId as persistActiveStudyTaskId } from "../study/session";

export type StudyEventType =
  | "session_start"
  | "filter_change"
  | "drill_down"
  | "explanation_view"
  | "explanation_toggle"
  | "evidence_link_open"
  | "evidence_dwell"
  | "query_submit"
  | "query_confirm"
  | "query_reject"
  | "query_revise"
  | "task_start"
  | "task_initial_response"
  | "task_response"
  | "comprehension_complete"
  | "export"
  | "latency";

const SESSION_KEY = "hc_session_id";
const PARTICIPANT_KEY = "hc_participant_id";
const ACTIVE_TASK_KEY = "hc_active_study_task";

export function getSessionId(): string {
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const created = crypto.randomUUID();
  sessionStorage.setItem(SESSION_KEY, created);
  return created;
}

export function getParticipantId(): string {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("participant");
  if (fromUrl) return fromUrl;

  const stored = localStorage.getItem(PARTICIPANT_KEY);
  if (stored) return stored;

  const generated = `anon-${crypto.randomUUID().slice(0, 8)}`;
  localStorage.setItem(PARTICIPANT_KEY, generated);
  return generated;
}

export function getActiveStudyTaskId(): string | null {
  return sessionStorage.getItem(ACTIVE_TASK_KEY);
}

export function setActiveStudyTaskId(taskId: string | null): void {
  persistActiveStudyTaskId(taskId);
}

export async function trackEvent(
  eventType: StudyEventType,
  payload: Record<string, unknown> = {},
  condition?: ExperimentalCondition,
  taskId?: string,
): Promise<void> {
  try {
    await postStudyEvent({
      event_type: eventType,
      session_id: getSessionId(),
      participant_id: getParticipantId(),
      condition,
      task_id: taskId ?? getActiveStudyTaskId() ?? undefined,
      payload,
    });
  } catch {
    // Telemetry must not block study tasks.
  }
}

export async function trackLatency(
  action: string,
  durationMs: number,
  condition?: ExperimentalCondition,
  extra: Record<string, unknown> = {},
): Promise<void> {
  await trackEvent(
    "latency",
    {
      action,
      duration_ms: durationMs,
      ...extra,
    },
    condition,
  );
}
