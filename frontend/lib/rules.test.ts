import { describe, expect, it } from "vitest";

import { filterLabel, parseFilterValue, ruleSummary } from "./rules";

describe("rules", () => {
  it("labels filters like the mockups", () => {
    expect(filterLabel({ field: "repo", op: "equals", value: "goalpost" })).toBe("repo = goalpost");
    expect(filterLabel({ field: "path", op: "matches", value: "backend/auth/*" })).toBe(
      "path ~ backend/auth/*",
    );
    expect(filterLabel({ field: "repo", op: "one_of", value: ["a", "b"] })).toBe("repo in a, b");
  });

  it("summarises a rule", () => {
    const rule = {
      id: "r",
      task_id: "t",
      connector_id: "c",
      connector_type: "github",
      connector_name: "Personal GitHub",
      kind: "commit",
      filters: [],
      min_count: 1,
      exclusions: [],
    };
    expect(ruleSummary(rule)).toBe("≥1 commit from Personal GitHub");
    expect(ruleSummary({ ...rule, connector_name: null })).toBe(
      "≥1 commit from a removed connector",
    );
  });

  it("parses typed values", () => {
    expect(parseFilterValue("one_of", "goalpost, dotfiles ,")).toEqual(["goalpost", "dotfiles"]);
    expect(parseFilterValue("at_least", "3")).toBe(3);
    expect(parseFilterValue("regex", "^chore:")).toBe("^chore:");
  });
});
