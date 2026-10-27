import { describe, expect, it } from "vitest";

import { priorityLabel, recurrenceLabel, tallyLabel } from "./format";

describe("format", () => {
  it("summarises recurrence days", () => {
    expect(recurrenceLabel([0, 1, 2, 3, 5])).toBe("Mon–Thu, Sat");
    expect(recurrenceLabel([0, 1, 2, 3, 4])).toBe("Mon–Fri");
    expect(recurrenceLabel([5, 6])).toBe("Sat, Sun");
    expect(recurrenceLabel([6, 0, 2])).toBe("Mon, Wed, Sun");
    expect(recurrenceLabel([0, 1, 2, 3, 4, 5, 6])).toBe("Every day");
  });

  it("labels adherence without counting skipped days", () => {
    expect(tallyLabel({ done: 3, planned: 5, skipped: 0, late: 1 })).toBe("3/5 · 1 late");
    expect(tallyLabel({ done: 1, planned: 3, skipped: 1, late: 0 })).toBe("1/2");
  });

  it("labels priority", () => {
    expect(priorityLabel("medium")).toBe("Medium");
  });
});
