import { describe, expect, it } from "vitest";

import { addDays, isoWeek, longDay, shortDay, weekDays, weekRange, weekdayIndex } from "./dates";

describe("dates", () => {
  it("adds days across month and year boundaries", () => {
    expect(addDays("2026-10-26", 6)).toBe("2026-11-01");
    expect(addDays("2026-12-28", 7)).toBe("2027-01-04");
    expect(addDays("2026-11-02", -7)).toBe("2026-10-26");
  });

  it("numbers weekdays from Monday", () => {
    expect(weekdayIndex("2026-10-26")).toBe(0);
    expect(weekdayIndex("2026-11-01")).toBe(6);
    expect(weekDays("2026-10-26")).toHaveLength(7);
  });

  it("computes ISO weeks", () => {
    expect(isoWeek("2026-10-26")).toBe(44);
    expect(isoWeek("2026-11-01")).toBe(44);
    expect(isoWeek("2026-10-24")).toBe(43);
    expect(isoWeek("2027-01-01")).toBe(53); // a Friday in 2026's last week
    expect(isoWeek("2027-01-04")).toBe(1);
  });

  it("formats days and week ranges like the mockups", () => {
    expect(longDay("2026-10-24")).toBe("Saturday, 24 October");
    expect(shortDay("2026-10-24")).toBe("Sat 24");
    expect(weekRange("2026-10-19")).toBe("19–25 Oct");
    expect(weekRange("2026-10-26")).toBe("26 Oct – 1 Nov");
  });
});
