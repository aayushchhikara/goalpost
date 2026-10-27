"use client";

import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import type { Occurrence } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** The done box: completes a pending or missed occurrence, and reopens a done one. */
export function OccurrenceCheck({ occurrence }: { occurrence: Occurrence }) {
  const { run, pending } = useAction();
  const title = occurrence.task.title;

  if (occurrence.status === "done") {
    return (
      <button
        type="button"
        aria-label={`Reopen ${title}`}
        disabled={pending}
        onClick={() => run(() => actions.reopen(occurrence.id))}
        className="flex size-5 shrink-0 items-center justify-center rounded-md bg-success"
      >
        <svg
          aria-hidden="true"
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          stroke="#0F1115"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M2.5 6.2l2.3 2.3 4.7-5" />
        </svg>
      </button>
    );
  }
  if (occurrence.status === "skipped") {
    return (
      <span
        aria-label="Skipped"
        role="img"
        className="size-5 shrink-0 rounded-md border-[1.5px] border-dashed border-ring"
      />
    );
  }
  return (
    <button
      type="button"
      aria-label={`Mark ${title} done${occurrence.status === "missed" ? " (late)" : ""}`}
      disabled={pending}
      onClick={() => run(() => actions.complete(occurrence.id))}
      className={cn(
        "size-5 shrink-0 rounded-md border-[1.5px] bg-transparent hover:border-foreground",
        occurrence.status === "missed" ? "border-missed" : "border-ring",
      )}
    />
  );
}
