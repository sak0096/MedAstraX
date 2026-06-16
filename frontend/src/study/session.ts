const ACTIVE_TASK_KEY = "hc_active_study_task";

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
