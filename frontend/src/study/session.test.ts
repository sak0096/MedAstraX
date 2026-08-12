import { afterEach, describe, expect, it } from "vitest";

import {
  getConditionFromUrl,
  getStudyArmFromUrl,
  isFacilitatorModeFromUrl,
  isStudyModeFromUrl,
} from "./session";

function setSearch(search: string): void {
  window.history.pushState({}, "", `/${search}`);
}

afterEach(() => {
  window.history.pushState({}, "", "/");
});

describe("study session URL helpers", () => {
  it("detects study mode and arm", () => {
    setSearch("?participant=P001&study=study2&condition=llm");
    expect(isStudyModeFromUrl()).toBe(true);
    expect(getStudyArmFromUrl()).toBe("study2");
    expect(getConditionFromUrl()).toBe("llm");
  });

  it("defaults arm to full when study is omitted", () => {
    setSearch("?participant=P001");
    expect(isStudyModeFromUrl()).toBe(false);
    expect(getStudyArmFromUrl()).toBe("full");
    expect(getConditionFromUrl()).toBeNull();
  });

  it("detects facilitator mode", () => {
    setSearch("?study=study1&facilitator=1");
    expect(isFacilitatorModeFromUrl()).toBe(true);
  });
});
