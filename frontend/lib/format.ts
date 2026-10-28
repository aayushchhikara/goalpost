import type { OccurrenceStatus, Priority, Tally } from "./api/types";
import { WEEKDAYS } from "./dates";

/** [0, 1, 2, 3, 5] → "Mon–Thu, Sat" */
export function recurrenceLabel(days: readonly number[]): string {
  const sorted = [...new Set(days)].sort((a, b) => a - b);
  if (sorted.length === 7) return "Every day";
  const runs: number[][] = [];
  for (const day of sorted) {
    const run = runs.at(-1);
    if (run && run.at(-1) === day - 1) run.push(day);
    else runs.push([day]);
  }
  return runs
    .flatMap((run) =>
      run.length >= 3
        ? [`${WEEKDAYS[run[0]]}–${WEEKDAYS[run.at(-1)!]}`]
        : run.map((d) => WEEKDAYS[d]),
    )
    .join(", ");
}

export function priorityLabel(priority: Priority): string {
  return priority[0].toUpperCase() + priority.slice(1);
}

export const STATUS_LABEL: Record<OccurrenceStatus, string> = {
  pending: "Pending",
  done: "Done",
  missed: "Missed",
  skipped: "Skipped",
};

/** Adherence as shown in the mockups: "3/5 · 1 late". Skipped days don't count. */
export function tallyLabel(tally: Pick<Tally, "done" | "planned" | "skipped" | "late">): string {
  const base = `${tally.done}/${tally.planned - tally.skipped}`;
  return tally.late ? `${base} · ${tally.late} late` : base;
}
