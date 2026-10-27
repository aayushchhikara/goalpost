"use client";

import { useState, type FormEvent } from "react";

import { DayPicker, Field, fieldClass } from "@/components/fields";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import type { Priority, TaskCreate, TaskKind } from "@/lib/api/types";
import { shortDay, weekDays } from "@/lib/dates";
import { cn } from "@/lib/utils";

/** Create a one-off (any day, a day, or the backlog) or a recurring task for a week. */
export function NewTaskForm({
  weekStart,
  today,
  closed,
  onDone,
}: {
  weekStart: string;
  today: string;
  closed: boolean;
  onDone: () => void;
}) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<TaskKind>("one_off");
  const [priority, setPriority] = useState<Priority>("medium");
  const [when, setWhen] = useState(closed ? "backlog" : "any");
  const [days, setDays] = useState<number[]>([]);
  const { run, pending } = useAction();

  const remaining = weekDays(weekStart).filter((d) => d >= today);
  const ready = title.trim() && (kind === "one_off" || days.length > 0);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!ready) return;
    const body: TaskCreate = { title, kind, priority };
    if (kind === "recurring") {
      body.recurrence_days = days;
      if (!closed) body.plan = { week_start: weekStart };
    } else if (when !== "backlog") {
      body.plan = { week_start: weekStart, date: when === "any" ? null : when };
    }
    if (await run(() => actions.createTask(body))) onDone();
  }

  return (
    <form
      onSubmit={submit}
      aria-label="New task"
      className="flex flex-col gap-3.5 rounded-[10px] border border-border bg-card p-4"
    >
      <div className="flex flex-wrap gap-2">
        <label htmlFor="new-title" className="sr-only">
          Title
        </label>
        <input
          id="new-title"
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="What do you want to do?"
          className={cn(fieldClass, "min-w-0 flex-1")}
        />
        <div
          role="radiogroup"
          aria-label="Kind"
          className="flex rounded-lg border border-input p-0.5"
        >
          {(["one_off", "recurring"] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={kind === k}
              onClick={() => setKind(k)}
              className={cn(
                "rounded-md px-3 py-1.5 text-[13px]",
                kind === k ? "bg-accent text-foreground" : "text-subtle",
              )}
            >
              {k === "one_off" ? "One-off" : "Recurring"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Priority" htmlFor="new-priority">
          <select
            id="new-priority"
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
            className={fieldClass}
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </Field>
        {kind === "one_off" ? (
          <Field label="When" htmlFor="new-when">
            <select
              id="new-when"
              value={when}
              onChange={(e) => setWhen(e.target.value)}
              className={fieldClass}
            >
              {!closed ? <option value="any">Any day this week</option> : null}
              {!closed &&
                remaining.map((d) => (
                  <option key={d} value={d}>
                    {shortDay(d)}
                  </option>
                ))}
              <option value="backlog">Backlog</option>
            </select>
          </Field>
        ) : (
          <Field label="Days">
            <DayPicker value={days} onChange={setDays} />
          </Field>
        )}
        <div className="ml-auto flex gap-2">
          <button
            type="button"
            onClick={onDone}
            className="rounded-lg border border-input px-3.5 py-2 text-subtle hover:text-foreground"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={pending || !ready}
            className="rounded-lg bg-primary px-3.5 py-2 font-medium text-primary-foreground disabled:opacity-60"
          >
            Add task
          </button>
        </div>
      </div>
    </form>
  );
}
