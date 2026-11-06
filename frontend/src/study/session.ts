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

export function takeLaunchCredential(search: string): { token: string | null; nextSearch: string } {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const token = params.get("launch_token");
  if (!token) {
    return { token: null, nextSearch: search.startsWith("?") || search === "" ? search : `?${search}` };
  }
  params.delete("launch_token");
  const rest = params.toString();
  return { token, nextSearch: rest ? `?${rest}` : "" };
}

export function hasPassedComprehension(arm = "default"): boolean {
  return sessionStorage.getItem(`${COMPREHENSION_KEY}:${arm}`) === "1";
}

export function markComprehensionPassed(arm = "default"): void {
  sessionStorage.setItem(`${COMPREHENSION_KEY}:${arm}`, "1");
}

export function comprehensionAttemptCount(arm = "default"): number {
  return Number(sessionStorage.getItem(`${COMPREHENSION_ATTEMPTS_KEY}:${arm}`) ?? "0");
}

export function incrementComprehensionAttempts(arm = "default"): number {
  const next = comprehensionAttemptCount(arm) + 1;
  sessionStorage.setItem(`${COMPREHENSION_ATTEMPTS_KEY}:${arm}`, String(next));
  return next;
}
