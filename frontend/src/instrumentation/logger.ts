import { postStudyEvent } from "../api/client";
import type { ExperimentalCondition } from "../types";

export type StudyEventType =
  | "session_start"
  | "filter_change"
  | "drill_down"
  | "explanation_view"
  | "query_submit"
  | "query_confirm"
  | "export"
  | "latency";

const SESSION_KEY = "hc_session_id";
const PARTICIPANT_KEY = "hc_participant_id";

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

export async function trackEvent(
  eventType: StudyEventType,
  payload: Record<string, unknown> = {},
  condition?: ExperimentalCondition,
): Promise<void> {
  try {
    await postStudyEvent({
      event_type: eventType,
      session_id: getSessionId(),
      participant_id: getParticipantId(),
      condition,
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
