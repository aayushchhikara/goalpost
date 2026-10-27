"use client";

import { useState, type FormEvent } from "react";

import { OccurrenceRow } from "@/components/occurrence-row";
import { LoadError, Loading, SectionHeading } from "@/components/screen-state";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import { useToday } from "@/lib/api/hooks";
import type { Adherence, Occurrence, Today } from "@/lib/api/types";
import { longDay } from "@/lib/dates";
import { tallyLabel } from "@/lib/format";

export function TodayScreen() {
  const { data, error } = useToday();
  if (error) return <LoadError error={error} />;
  if (!data) return <Loading />;

  const adherence = new Map(data.adherence.map((a) => [a.task_id, a]));
  const { done, planned, skipped } = data.summary;

  return (
    <>
      <section aria-labelledby="today-h" className="flex min-w-0 flex-[999_1_520px] flex-col gap-6">
        <header>
          <h1 id="today-h" className="m-0 text-[26px] font-semibold tracking-[-0.02em]">
            {longDay(data.date)}
          </h1>
          <p className="mt-0.5 text-muted-foreground">
            Week {data.iso_week} · {done} of {planned - skipped} planned items done
          </p>
        </header>

        <QuickAdd today={data} />

        <OccurrenceList
          title="Today"
          items={data.items}
          adherence={adherence}
          empty="Nothing planned for today."
        />
        <OccurrenceList
          title="Any day this week"
          items={data.any_day}
          adherence={adherence}
          empty="No any-day tasks this week."
        />
      </section>

      <aside aria-label="This week" className="flex max-w-[360px] flex-[1_1_280px] flex-col gap-4">
        <RecurringCard adherence={data.adherence} />
      </aside>
    </>
  );
}

function OccurrenceList({
  title,
  items,
  adherence,
  empty,
}: {
  title: string;
  items: Occurrence[];
  adherence: Map<string, Adherence>;
  empty: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <SectionHeading>{title}</SectionHeading>
      {items.length === 0 ? <p className="text-muted-foreground">{empty}</p> : null}
      {items.map((o) => (
        <OccurrenceRow key={o.id} occurrence={o} adherence={adherence.get(o.task.id)} />
      ))}
    </div>
  );
}

/** Adds a one-off task for today. */
function QuickAdd({ today }: { today: Today }) {
  const [title, setTitle] = useState("");
  const { run, pending } = useAction();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    const created = await run(() =>
      actions.createTask({
        title,
        plan: { week_start: today.week_start, date: today.date },
      }),
    );
    if (created) setTitle("");
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <label htmlFor="quick" className="sr-only">
        Quick add a task
      </label>
      <input
        id="quick"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Add a task for today…"
        className="min-w-0 flex-1 rounded-lg border border-input bg-card px-3.5 py-2.5 outline-none focus-visible:border-ring"
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

function RecurringCard({ adherence }: { adherence: Adherence[] }) {
  return (
    <div className="flex flex-col gap-3 rounded-[10px] border border-border bg-card p-[18px]">
      <h2 className="m-0 text-sm font-semibold">Recurring this week</h2>
      {adherence.length === 0 ? (
        <p className="text-muted-foreground">No recurring tasks planned this week.</p>
      ) : null}
      {adherence.map((a) => (
        <div key={a.task_id} className="flex justify-between gap-3">
          <span>{a.title}</span>
          <span className="font-mono text-subtle">{tallyLabel(a)}</span>
        </div>
      ))}
    </div>
  );
}
