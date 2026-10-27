"use client";

import { useEffect, useRef, useState } from "react";

import { DayPicker, Field, fieldClass } from "@/components/fields";
import { LoadError, Loading, SectionHeading } from "@/components/screen-state";
import { useDrawer } from "@/components/shell/drawer-context";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import { useTask, useToday } from "@/lib/api/hooks";
import type { Occurrence, Priority, TaskDetail, TaskUpdate, Today } from "@/lib/api/types";
import { addDays, isoWeek, shortDay, weekDays } from "@/lib/dates";
import { STATUS_LABEL, recurrenceLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export function TaskDrawer() {
  const { taskId, close } = useDrawer();
  if (!taskId) return null;
  return <DrawerPanel key={taskId} taskId={taskId} onClose={close} />;
}

function DrawerPanel({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const task = useTask(taskId);
  const today = useToday();
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const error = task.error ?? today.error;
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div aria-hidden="true" onClick={onClose} className="absolute inset-0 bg-black/55" />
      <aside
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="task-h"
        tabIndex={-1}
        className="relative flex h-full w-full max-w-[560px] flex-col gap-[22px] overflow-y-auto border-l border-input bg-drawer px-7 pt-6 pb-10 outline-none"
      >
        {error ? <LoadError error={error} /> : null}
        {!error && (!task.data || !today.data) ? <Loading /> : null}
        {task.data && today.data ? (
          <TaskEditor detail={task.data} today={today.data} onClose={onClose} />
        ) : null}
      </aside>
    </div>
  );
}

/** The occurrence "When" acts on: this week's, or a pending one in a later week. */
function plannedOccurrence(detail: TaskDetail, today: Today): Occurrence | undefined {
  return detail.history.find(
    (o) =>
      (o.status === "pending" || o.status === "missed") && addDays(o.week_start, 6) >= today.date,
  );
}

function describe(detail: TaskDetail, planned: Occurrence | undefined, today: Today): string {
  const { task } = detail;
  if (task.kind === "recurring") return `Recurring ${recurrenceLabel(task.recurrence_days ?? [])}`;
  const parts = ["One-off"];
  if (task.status === "done") parts.push("done");
  else if (task.status === "dropped") parts.push("dropped");
  else if (task.in_backlog) parts.push("in the backlog");
  else if (planned) {
    const week =
      planned.week_start === today.week_start ? "this week" : `week ${isoWeek(planned.week_start)}`;
    parts.push(planned.date ? `${shortDay(planned.date)}, ${week}` : `any day ${week}`);
  }
  if (planned?.carried_over && task.first_planned_week_start) {
    parts.push(`carried over from week ${isoWeek(task.first_planned_week_start)}`);
  }
  return parts.join(" · ");
}

function TaskEditor({
  detail,
  today,
  onClose,
}: {
  detail: TaskDetail;
  today: Today;
  onClose: () => void;
}) {
  const { task } = detail;
  const [title, setTitle] = useState(task.title);
  const [notes, setNotes] = useState(task.notes);
  const [priority, setPriority] = useState<Priority>(task.priority);
  const [days, setDays] = useState<number[]>(task.recurrence_days ?? []);
  const { run, pending } = useAction();

  const recurring = task.kind === "recurring";
  const savedDays = (task.recurrence_days ?? []).join();
  const daysChanged = recurring && [...days].sort((a, b) => a - b).join() !== savedDays;
  const dirty =
    title.trim() !== task.title ||
    notes !== task.notes ||
    priority !== task.priority ||
    daysChanged;
  const planned = plannedOccurrence(detail, today);

  async function save() {
    const body: TaskUpdate = { title, notes, priority };
    if (daysChanged) body.recurrence_days = days;
    await run(() => actions.updateTask(task.id, body));
  }

  async function drop() {
    if (!window.confirm(`Drop "${task.title}"? Its remaining days go; history is kept.`)) return;
    if (await run(() => actions.dropTask(task.id))) onClose();
  }

  return (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <label htmlFor="task-h" className="sr-only">
            Title
          </label>
          <input
            id="task-h"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-md bg-transparent text-xl font-semibold tracking-[-0.01em] outline-none focus-visible:bg-field"
          />
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            {describe(detail, planned, today)}
          </p>
        </div>
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="flex rounded-md p-1.5 text-subtle hover:bg-accent hover:text-foreground"
        >
          <svg
            aria-hidden="true"
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          >
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Priority" htmlFor="task-priority">
          <select
            id="task-priority"
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority)}
            className={fieldClass}
          >
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </Field>
        {!recurring ? <WhenField detail={detail} planned={planned} today={today} /> : null}
      </div>

      {recurring ? (
        <Field label="Recurring days (changes apply from today on)">
          <DayPicker value={days} onChange={setDays} />
        </Field>
      ) : null}

      <Field label="Notes" htmlFor="task-notes">
        <textarea
          id="task-notes"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className={cn(fieldClass, "resize-y")}
        />
      </Field>

      <div className="flex gap-2">
        <button
          type="button"
          disabled={!dirty || pending || !title.trim() || (recurring && days.length === 0)}
          onClick={save}
          className="rounded-lg bg-primary px-3.5 py-2 font-medium text-primary-foreground disabled:opacity-50"
        >
          Save changes
        </button>
        {dirty ? (
          <button
            type="button"
            onClick={() => {
              setTitle(task.title);
              setNotes(task.notes);
              setPriority(task.priority);
              setDays(task.recurrence_days ?? []);
            }}
            className="rounded-lg border border-input px-3.5 py-2 text-subtle hover:text-foreground"
          >
            Discard
          </button>
        ) : null}
      </div>

      <History detail={detail} today={today} />

      {task.status === "open" ? (
        <div className="border-t border-border pt-3.5">
          <button
            type="button"
            disabled={pending}
            onClick={drop}
            className="rounded-lg border border-input px-3.5 py-2 text-missed hover:bg-late"
          >
            Drop task
          </button>
        </div>
      ) : null}
    </>
  );
}

/** One-off scheduling: move within the planned week, or plan from the backlog. */
function WhenField({
  detail,
  planned,
  today,
}: {
  detail: TaskDetail;
  planned: Occurrence | undefined;
  today: Today;
}) {
  const { run, pending } = useAction();
  const { task } = detail;
  if (task.status !== "open") return null;

  if (planned) {
    const thisWeek = planned.week_start === today.week_start;
    const remaining = weekDays(planned.week_start).filter((d) => d >= today.date);
    const value = planned.date ?? "any";
    return (
      <Field label="When" htmlFor="task-when">
        <select
          id="task-when"
          value={value}
          disabled={pending}
          onChange={(e) => {
            const day = e.target.value === "any" ? null : e.target.value;
            run(() => actions.move(planned.id, day));
          }}
          className={fieldClass}
        >
          <option value="any">
            {thisWeek ? "Any day this week" : `Any day in week ${isoWeek(planned.week_start)}`}
          </option>
          {planned.date && !remaining.includes(planned.date) ? (
            <option value={planned.date} disabled>
              {shortDay(planned.date)} ({STATUS_LABEL[planned.status].toLowerCase()})
            </option>
          ) : null}
          {remaining.map((d) => (
            <option key={d} value={d}>
              {shortDay(d)}
            </option>
          ))}
        </select>
      </Field>
    );
  }

  const nextWeek = addDays(today.week_start, 7);
  const thisWeekDays = weekDays(today.week_start).filter((d) => d >= today.date);
  return (
    <Field label="When" htmlFor="task-when">
      <select
        id="task-when"
        value="backlog"
        disabled={pending}
        onChange={(e) => {
          const [monday, day] = e.target.value.split("|");
          run(() => actions.planWeek(monday, [{ task_id: task.id, date: day || null }]));
        }}
        className={fieldClass}
      >
        <option value="backlog">Backlog</option>
        <option value={`${today.week_start}|`}>Any day this week</option>
        {thisWeekDays.map((d) => (
          <option key={d} value={`${today.week_start}|${d}`}>
            {shortDay(d)}
          </option>
        ))}
        <option value={`${nextWeek}|`}>Any day next week</option>
      </select>
    </Field>
  );
}

function History({ detail, today }: { detail: TaskDetail; today: Today }) {
  const { run, pending } = useAction();
  if (detail.history.length === 0) return null;
  const oneOff = detail.task.kind === "one_off";

  return (
    <section
      aria-labelledby="hist-h"
      className="flex flex-col gap-1.5 border-t border-border pt-3.5"
    >
      <SectionHeading>
        <span id="hist-h">History</span>
      </SectionHeading>
      {detail.history.map((o) => {
        const weekClosed = addDays(o.week_start, 6) < today.date;
        const status =
          o.status === "missed" && oneOff && weekClosed
            ? "Missed → backlog"
            : `${STATUS_LABEL[o.status]}${o.late && o.status === "done" ? " · late" : ""}`;
        return (
          <div key={o.id} className="flex items-center justify-between gap-3 text-[13px]">
            <span>
              Week {isoWeek(o.week_start)} · {o.date ? shortDay(o.date) : "any day"}
            </span>
            <span className="flex items-center gap-2">
              <span
                className={cn(
                  o.status === "done" && "text-success",
                  o.status === "missed" && "text-missed",
                  (o.status === "pending" || o.status === "skipped") && "text-subtle",
                )}
              >
                {status}
              </span>
              <HistoryAction occurrence={o} today={today.date} pending={pending} run={run} />
            </span>
          </div>
        );
      })}
    </section>
  );
}

function HistoryAction({
  occurrence,
  today,
  pending,
  run,
}: {
  occurrence: Occurrence;
  today: string;
  pending: boolean;
  run: ReturnType<typeof useAction>["run"];
}) {
  const button = (label: string, action: () => Promise<unknown>) => (
    <button
      type="button"
      disabled={pending}
      onClick={() => run(action)}
      className="rounded-md border border-input px-2 py-0.5 text-xs hover:bg-accent"
    >
      {label}
    </button>
  );
  switch (occurrence.status) {
    case "pending":
      // A day that hasn't come yet can be skipped, but not done.
      return (
        <>
          {!occurrence.date || occurrence.date <= today
            ? button("Done", () => actions.complete(occurrence.id))
            : null}
          {button("Skip", () => actions.skip(occurrence.id))}
        </>
      );
    case "missed":
      return button("Done late", () => actions.complete(occurrence.id));
    default:
      return button("Reopen", () => actions.reopen(occurrence.id));
  }
}
