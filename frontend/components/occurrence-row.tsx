"use client";

import { OccurrenceCheck } from "@/components/occurrence-check";
import { useDrawer } from "@/components/shell/drawer-context";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import type { Adherence, Occurrence } from "@/lib/api/types";
import { formatDay, shortDay } from "@/lib/dates";
import { priorityLabel, recurrenceLabel, tallyLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

function details(occurrence: Occurrence, adherence?: Adherence): string {
  const { task } = occurrence;
  const parts: string[] = [];
  if (task.kind === "recurring") {
    parts.push(`Recurring ${recurrenceLabel(task.recurrence_days ?? [])}`);
    if (adherence) parts.push(`${tallyLabel(adherence)} this week`);
  } else {
    parts.push(priorityLabel(task.priority));
  }
  if (occurrence.carried_over) parts.push("carried over");
  if (occurrence.status === "done" && occurrence.completed_at) {
    parts.push(`Done ${shortDay(formatDay(new Date(occurrence.completed_at)))}`);
  }
  return parts.join(" · ");
}

export function OccurrenceRow({
  occurrence,
  adherence,
}: {
  occurrence: Occurrence;
  adherence?: Adherence;
}) {
  const { openTask } = useDrawer();
  const { run, pending } = useAction();
  const finished = occurrence.status === "done" || occurrence.status === "skipped";

  return (
    <div
      className={cn(
        "flex items-center gap-3.5 rounded-[10px] border px-4 py-3.5",
        finished ? "border-border-done bg-surface-done" : "border-border bg-card",
      )}
    >
      <OccurrenceCheck occurrence={occurrence} />
      <button
        type="button"
        onClick={() => openTask(occurrence.task.id)}
        className="min-w-0 flex-1 text-left"
      >
        <div className={cn("font-medium", finished && "text-subtle line-through")}>
          {occurrence.task.title}
        </div>
        <div className="text-xs text-muted-foreground">{details(occurrence, adherence)}</div>
      </button>
      {occurrence.late && occurrence.status === "done" ? (
        <span className="rounded bg-late px-1.5 text-xs text-missed">Late</span>
      ) : null}
      {occurrence.status === "missed" ? <span className="text-xs text-missed">Missed</span> : null}
      {occurrence.status === "pending" ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => run(() => actions.skip(occurrence.id))}
          className="rounded-md px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          Skip
        </button>
      ) : null}
      {occurrence.status === "skipped" ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => run(() => actions.reopen(occurrence.id))}
          className="rounded-md px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          Skipped · Reopen
        </button>
      ) : null}
    </div>
  );
}
