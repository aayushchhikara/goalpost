"use client";

import { useState, type FormEvent } from "react";

import { fieldClass } from "@/components/fields";
import { LoadError, Loading } from "@/components/screen-state";
import { useDrawer } from "@/components/shell/drawer-context";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import { useBacklog, useToday } from "@/lib/api/hooks";
import type { Priority } from "@/lib/api/types";
import { addDays, isoWeek } from "@/lib/dates";
import { priorityLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export function BacklogScreen() {
  const [priority, setPriority] = useState<Priority | undefined>();
  const backlog = useBacklog(priority);
  const today = useToday();
  const { openTask } = useDrawer();
  const { run, pending } = useAction();

  const error = backlog.error ?? today.error;
  if (error) return <LoadError error={error} />;
  if (!backlog.data || !today.data) return <Loading />;

  const thisWeek = today.data.week_start;
  const nextWeek = addDays(thisWeek, 7);
  const items = backlog.data.items;

  return (
    <section aria-labelledby="backlog-h" className="flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 id="backlog-h" className="m-0 text-[26px] font-semibold tracking-[-0.02em]">
            Backlog
          </h1>
          <p className="mt-0.5 text-muted-foreground">
            Ideas without a date, and one-off tasks whose week ended unfinished.
          </p>
        </div>
        <label className="flex items-center gap-2 text-muted-foreground">
          Priority
          <select
            value={priority ?? ""}
            onChange={(e) => setPriority((e.target.value || undefined) as Priority | undefined)}
            className={fieldClass}
          >
            <option value="">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
      </header>

      <NewIdea />

      <div className="flex flex-col gap-2">
        {items.length === 0 ? (
          <p className="text-muted-foreground">Nothing in the backlog.</p>
        ) : null}
        {items.map(({ task, last_planned_week_start, attempts }) => (
          <div
            key={task.id}
            className="flex flex-wrap items-center gap-3 rounded-[10px] border border-border bg-card px-4 py-3"
          >
            <button
              type="button"
              onClick={() => openTask(task.id)}
              className="min-w-0 flex-1 text-left"
            >
              <div className="font-medium">{task.title}</div>
              <div className="text-xs text-muted-foreground">
                {priorityLabel(task.priority)}
                {last_planned_week_start
                  ? ` · missed week ${isoWeek(last_planned_week_start)}${attempts > 1 ? ` (${attempts} tries)` : ""}`
                  : " · not planned yet"}
              </div>
            </button>
            <div className="flex gap-2">
              {[
                { label: "This week", monday: thisWeek },
                { label: "Next week", monday: nextWeek },
              ].map(({ label, monday }) => (
                <button
                  key={label}
                  type="button"
                  disabled={pending}
                  onClick={() => run(() => actions.planWeek(monday, [{ task_id: task.id }]))}
                  className="rounded-md border border-input px-2.5 py-1 text-xs hover:bg-accent"
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  if (window.confirm(`Drop "${task.title}"?`)) run(() => actions.dropTask(task.id));
                }}
                className="rounded-md border border-input px-2.5 py-1 text-xs text-missed hover:bg-late"
              >
                Drop
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Adds an undated one-off straight to the backlog. */
function NewIdea() {
  const [title, setTitle] = useState("");
  const { run, pending } = useAction();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    if (await run(() => actions.createTask({ title }))) setTitle("");
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <label htmlFor="idea" className="sr-only">
        Add to the backlog
      </label>
      <input
        id="idea"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Add an idea to the backlog…"
        className={cn(fieldClass, "min-w-0 flex-1 bg-card px-3.5 py-2.5")}
      />
      <button
        type="submit"
        disabled={pending || !title.trim()}
        className="rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground disabled:opacity-60"
      >
        Add
      </button>
    </form>
  );
}
