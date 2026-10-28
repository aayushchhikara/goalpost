"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type DragEvent, type ReactNode } from "react";

import { NewTaskForm } from "@/components/new-task-form";
import { LoadError, Loading } from "@/components/screen-state";
import { useDrawer } from "@/components/shell/drawer-context";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import { useBacklog, useToday, useWeek } from "@/lib/api/hooks";
import type { BacklogItem, Occurrence, Today, Week } from "@/lib/api/types";
import { WEEKDAYS, addDays, isoWeek, parseDay, weekRange } from "@/lib/dates";
import { STATUS_LABEL, priorityLabel, tallyLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

// Drag payloads: an occurrence moves within the week, a backlog task gets planned.
const OCCURRENCE = "application/x-goalpost-occurrence";
const TASK = "application/x-goalpost-task";

export function WeekScreen() {
  const start = useSearchParams().get("start");
  const today = useToday();
  const monday = start ?? today.data?.week_start;
  const week = useWeek(monday);
  const backlog = useBacklog();

  const error = today.error ?? week.error;
  if (error) return <LoadError error={error} />;
  if (!today.data || !week.data) return <Loading />;
  return <WeekView week={week.data} today={today.data} backlog={backlog.data?.items ?? []} />;
}

function WeekView({ week, today, backlog }: { week: Week; today: Today; backlog: BacklogItem[] }) {
  const [adding, setAdding] = useState(false);
  const { run, pending } = useAction();
  const monday = week.week_start;
  const closed = week.status === "closed";
  const { done, planned, skipped } = week.summary;

  const summary = [
    `${done} of ${planned - skipped} done`,
    ...week.adherence.map((a) => `${a.title} ${tallyLabel(a)}`),
  ].join(" · ");

  // Dropping moves an occurrence, or plans a backlog task, onto a day (null = any day).
  async function drop(event: DragEvent, day: string | null) {
    event.preventDefault();
    const occurrenceId = event.dataTransfer.getData(OCCURRENCE);
    const taskId = event.dataTransfer.getData(TASK);
    if (occurrenceId) await run(() => actions.move(occurrenceId, day));
    else if (taskId) await run(() => actions.planWeek(monday, [{ task_id: taskId, date: day }]));
  }

  return (
    <>
      <section aria-labelledby="week-h" className="flex min-w-0 flex-[999_1_640px] flex-col gap-5">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 id="week-h" className="m-0 text-[26px] font-semibold tracking-[-0.02em]">
              Week {week.iso_week} · {weekRange(monday)}
            </h1>
            <p className="mt-0.5 text-muted-foreground">
              {planned ? summary : "Nothing planned yet"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <nav aria-label="Weeks" className="flex rounded-lg border border-input">
              <WeekLink monday={addDays(monday, -7)} label="Previous week">
                ←
              </WeekLink>
              <WeekLink monday={today.week_start} label="This week">
                This week
              </WeekLink>
              <WeekLink monday={addDays(monday, 7)} label="Next week">
                →
              </WeekLink>
            </nav>
            {!closed ? (
              <button
                type="button"
                disabled={pending}
                onClick={() => run(() => actions.planWeek(monday, []))}
                title="Give every recurring task its days in this week"
                className="rounded-lg border border-input px-3.5 py-2 hover:bg-accent"
              >
                Add recurring days
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="rounded-lg bg-primary px-3.5 py-2 font-medium text-primary-foreground"
            >
              Add task
            </button>
          </div>
        </header>

        {adding ? (
          <NewTaskForm
            weekStart={monday}
            today={today.date}
            closed={closed}
            onDone={() => setAdding(false)}
          />
        ) : null}

        <DropZone
          enabled={!closed}
          onDrop={(e) => drop(e, null)}
          className="flex flex-wrap items-center gap-2.5 rounded-[10px] border border-dashed border-input px-4 py-3.5"
        >
          <span className="mr-1.5 text-xs font-semibold tracking-[0.06em] text-muted-foreground uppercase">
            Any day
          </span>
          {week.any_day.length === 0 ? (
            <span className="text-muted-foreground">Drop tasks here for any day this week</span>
          ) : null}
          {week.any_day.map((o) => (
            <OccurrenceCard key={o.id} occurrence={o} closed={closed} chip />
          ))}
        </DropZone>

        <div className="-m-1.5 overflow-x-auto p-1.5">
          <div className="grid min-w-[760px] grid-cols-[repeat(7,minmax(100px,1fr))] gap-2.5">
            {week.days.map(({ date, occurrences }, i) => {
              const isToday = date === today.date;
              return (
                <DropZone
                  key={date}
                  enabled={!closed && date >= today.date}
                  onDrop={(e) => drop(e, date)}
                  className={cn(
                    "flex min-h-24 flex-col gap-2",
                    isToday && "-m-1.5 rounded-[10px] border border-input bg-today p-1.5",
                  )}
                >
                  <div
                    className={cn(
                      "px-0.5 text-[13px]",
                      isToday ? "font-semibold text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {WEEKDAYS[i]} <span className="font-mono">{parseDay(date).getDate()}</span>
                    {isToday ? " · today" : null}
                  </div>
                  {occurrences.map((o) => (
                    <OccurrenceCard key={o.id} occurrence={o} closed={closed} />
                  ))}
                </DropZone>
              );
            })}
          </div>
        </div>
      </section>

      <BacklogPanel items={backlog} monday={monday} closed={closed} />
    </>
  );
}

function WeekLink({
  monday,
  label,
  children,
}: {
  monday: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={`/week?start=${monday}`}
      aria-label={label}
      className="px-3 py-2 text-subtle hover:bg-accent hover:text-foreground"
    >
      {children}
    </Link>
  );
}

function DropZone({
  enabled,
  onDrop,
  className,
  children,
}: {
  enabled: boolean;
  onDrop: (event: DragEvent) => void;
  className: string;
  children: ReactNode;
}) {
  const [over, setOver] = useState(false);
  const accepts = (e: DragEvent) =>
    enabled && (e.dataTransfer.types.includes(OCCURRENCE) || e.dataTransfer.types.includes(TASK));
  return (
    <div
      onDragOver={(e) => {
        if (!accepts(e)) return;
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        setOver(false);
        if (accepts(e)) onDrop(e);
      }}
      className={cn(className, over && "outline-2 outline-primary/60")}
    >
      {children}
    </div>
  );
}

function OccurrenceCard({
  occurrence,
  closed,
  chip = false,
}: {
  occurrence: Occurrence;
  closed: boolean;
  chip?: boolean;
}) {
  const { openTask } = useDrawer();
  const { status, task } = occurrence;
  const finished = status === "done" || status === "skipped";
  const movable =
    !closed && (status === "pending" || (status === "missed" && task.kind === "one_off"));

  return (
    <button
      type="button"
      draggable={movable}
      onDragStart={(e) => e.dataTransfer.setData(OCCURRENCE, occurrence.id)}
      onClick={() => openTask(task.id)}
      className={cn(
        "rounded-lg border text-left",
        chip ? "px-2.5 py-1.5" : "p-2.5",
        finished
          ? "border-border-done bg-surface-done text-muted-foreground"
          : "border-border bg-card",
        movable && "cursor-grab active:cursor-grabbing",
      )}
    >
      <span
        className={cn(
          chip ? "" : "block",
          finished && "line-through",
          status === "missed" && "text-subtle",
        )}
      >
        {task.title}
      </span>
      {chip ? (
        <span className="text-muted-foreground">
          {occurrence.carried_over ? " · carried over" : null}
          {status !== "pending" ? ` · ${STATUS_LABEL[status]}` : null}
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-xs">
          <span
            className={cn(
              status === "done" && "text-success",
              status === "missed" && "text-missed",
              (status === "pending" || status === "skipped") && "text-muted-foreground",
            )}
          >
            {STATUS_LABEL[status]}
          </span>
          {occurrence.late && status === "done" ? (
            <span className="rounded bg-late px-1.5 text-missed">Late</span>
          ) : null}
        </span>
      )}
    </button>
  );
}

function BacklogPanel({
  items,
  monday,
  closed,
}: {
  items: BacklogItem[];
  monday: string;
  closed: boolean;
}) {
  const { openTask } = useDrawer();
  const { run, pending } = useAction();

  return (
    <aside
      id="backlog"
      aria-labelledby="backlog-h"
      className="flex max-w-[320px] flex-[1_1_260px] flex-col gap-2.5"
    >
      <div className="flex items-baseline justify-between">
        <h2 id="backlog-h" className="m-0 text-sm font-semibold">
          Backlog
        </h2>
        <span className="text-xs text-muted-foreground">
          {items.length} {items.length === 1 ? "item" : "items"}
        </span>
      </div>
      {items.length === 0 ? <p className="text-muted-foreground">The backlog is empty.</p> : null}
      {items.map(({ task, last_planned_week_start }) => (
        <div
          key={task.id}
          draggable={!closed}
          onDragStart={(e) => e.dataTransfer.setData(TASK, task.id)}
          className={cn(
            "flex flex-col gap-2 rounded-[10px] border border-border bg-card p-3",
            !closed && "cursor-grab active:cursor-grabbing",
          )}
        >
          <button type="button" onClick={() => openTask(task.id)} className="text-left">
            {task.title}
          </button>
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>
              {priorityLabel(task.priority)}
              {last_planned_week_start
                ? ` · missed week ${isoWeek(last_planned_week_start)}`
                : null}
            </span>
            <button
              type="button"
              disabled={closed || pending}
              onClick={() => run(() => actions.planWeek(monday, [{ task_id: task.id }]))}
              className="rounded-md border border-input px-2 py-0.5 text-foreground hover:bg-accent disabled:opacity-50"
            >
              Add to week
            </button>
          </div>
        </div>
      ))}
    </aside>
  );
}
