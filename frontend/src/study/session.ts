const ACTIVE_TASK_KEY = "hc_active_study_task";
const COMPREHENSION_KEY = "hc_comprehension_passed";
const COMPREHENSION_ATTEMPTS_KEY = "hc_comprehension_attempts";

export function getActiveStudyTaskId(): string | null {
  return sessionStorage.getItem(ACTIVE_TASK_KEY);
}

export function setActiveStudyTaskId(taskId: string | null): void {
  if (taskId) {
    sessionStorage.setItem(ACTIVE_TASK_KEY, taskId);
  } else {
    sessionStorage.removeItem(ACTIVE_TASK_KEY);
  }
}

export function isStudyModeFromUrl(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.get("study") !== null;
}

export function getStudyArmFromUrl(): "study1" | "study2" | "full" {
  const params = new URLSearchParams(window.location.search);
  const study = params.get("study");
  if (study === "study1" || study === "study2") return study;
  return "full";
}

export function getConditionFromUrl(): "baseline" | "xai" | "llm" | null {
  const params = new URLSearchParams(window.location.search);
  const condition = params.get("condition");
  if (condition === "baseline" || condition === "xai" || condition === "llm") {
    return condition;
  }
  return null;
}

export function isFacilitatorModeFromUrl(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.get("facilitator") === "1";
}

export function hasPassedComprehension(): boolean {
  return sessionStorage.getItem(COMPREHENSION_KEY) === "1";
}

export function markComprehensionPassed(): void {
  sessionStorage.setItem(COMPREHENSION_KEY, "1");
}

export function comprehensionAttemptCount(): number {
  return Number(sessionStorage.getItem(COMPREHENSION_ATTEMPTS_KEY) ?? "0");
}

export function incrementComprehensionAttempts(): number {
  const next = comprehensionAttemptCount() + 1;
  sessionStorage.setItem(COMPREHENSION_ATTEMPTS_KEY, String(next));
  return next;
}
