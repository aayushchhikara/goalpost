import { describe, expect, it } from "vitest";

import { priorityLabel, recurrenceLabel, tallyLabel, timeAgo } from "./format";

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

describe("timeAgo", () => {
  const now = new Date("2026-11-01T12:00:00Z");
  it("rounds to a readable unit", () => {
    expect(timeAgo("2026-11-01T11:59:40Z", now)).toBe("just now");
    expect(timeAgo("2026-11-01T11:55:00Z", now)).toBe("5 min ago");
    expect(timeAgo("2026-11-01T10:00:00Z", now)).toBe("2 h ago");
    expect(timeAgo("2026-10-31T12:00:00Z", now)).toBe("1 day ago");
    expect(timeAgo("2026-10-29T12:00:00Z", now)).toBe("3 days ago");
  });
});
