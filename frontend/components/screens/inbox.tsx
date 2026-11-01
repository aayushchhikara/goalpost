"use client";

import { useState } from "react";

import { fieldClass } from "@/components/fields";
import { LoadError, Loading, SectionHeading } from "@/components/screen-state";
import { useDrawer } from "@/components/shell/drawer-context";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import {
  useConnectorTypes,
  useSuggestions,
  useToday,
  useUnplanned,
  useWeek,
} from "@/lib/api/hooks";
import type {
  ConnectorType,
  EventItem,
  FilterOp,
  Occurrence,
  Suggestion,
  Week,
} from "@/lib/api/types";
import { shortDay } from "@/lib/dates";
import { OP_LABEL, filterLabel, parseFilterValue, ruleSummary } from "@/lib/rules";
import { cn } from "@/lib/utils";

export function InboxScreen() {
  const suggestions = useSuggestions();
  const today = useToday();
  const week = useWeek(today.data?.week_start);
  const unplanned = useUnplanned(today.data?.week_start);
  const types = useConnectorTypes();

  const error = suggestions.error ?? today.error;
  if (error) return <LoadError error={error} />;
  if (!suggestions.data || !today.data) return <Loading />;

  const items = suggestions.data.items;
  const targets = week.data ? occurrenceOptions(week.data) : [];

  return (
    <section aria-labelledby="inbox-h" className="flex w-full max-w-3xl flex-col gap-6">
      <header>
        <h1 id="inbox-h" className="m-0 text-[26px] font-semibold tracking-[-0.02em]">
          Proof Inbox
        </h1>
        <p className="mt-0.5 text-muted-foreground">
          {items.length} {items.length === 1 ? "suggestion" : "suggestions"} · nothing counts until
          you accept it
        </p>
      </header>

      {items.length === 0 ? (
        <p className="rounded-[10px] border border-border bg-card px-4 py-3.5 text-subtle">
          Nothing to review. Suggestions appear here when synced activity matches a task&apos;s
          rule.
        </p>
      ) : null}
      {items.map((s) => (
        <SuggestionCard
          key={s.id}
          suggestion={s}
          targets={targets.filter((o) => o.id !== s.occurrence.id)}
          types={types.data?.items ?? []}
        />
      ))}

      <div className="flex flex-col gap-2">
        <SectionHeading>Unplanned work this week</SectionHeading>
        {unplanned.data?.items.length === 0 ? (
          <p className="text-muted-foreground">Every synced event this week backs a task.</p>
        ) : null}
        {unplanned.data?.items.map((e) => (
          <UnplannedRow key={e.id} event={e} targets={targets} />
        ))}
      </div>
    </section>
  );
}

type Target = { id: string; label: string };

/** Occurrences this week that evidence can go to. */
function occurrenceOptions(week: Week): Target[] {
  const all: Occurrence[] = [...week.days.flatMap((d) => d.occurrences), ...week.any_day];
  return all
    .filter((o) => o.status !== "skipped")
    .map((o) => ({
      id: o.id,
      label: `${o.task.title} · ${o.date ? shortDay(o.date) : "any day"}${o.status === "done" ? " (done)" : ""}`,
    }));
}

function time(event: EventItem): string {
  const at = new Date(event.occurred_at).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${shortDay(event.local_date)} ${at}`;
}

function EventRow({ event }: { event: EventItem }) {
  return (
    <li className="flex items-baseline justify-between gap-3 border-t border-border py-2 first:border-t-0">
      <span className="min-w-0 truncate">
        {event.url ? (
          <a href={event.url} target="_blank" rel="noreferrer" className="hover:underline">
            {event.title}
          </a>
        ) : (
          event.title
        )}
        <span className="ml-2 text-xs text-muted-foreground">{event.connector_name}</span>
      </span>
      <span className="shrink-0 font-mono text-xs text-muted-foreground">{time(event)}</span>
    </li>
  );
}

function SuggestionCard({
  suggestion,
  targets,
  types,
}: {
  suggestion: Suggestion;
  targets: Target[];
  types: ConnectorType[];
}) {
  const { openTask } = useDrawer();
  const { run, pending } = useAction();
  const [mode, setMode] = useState<"idle" | "reject" | "reassign">("idle");
  const { occurrence, rule, events } = suggestion;
  const when = occurrence.date ? shortDay(occurrence.date) : "Any day this week";

  return (
    <article className="flex flex-col gap-3 rounded-[10px] border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => openTask(occurrence.task.id)}
            className="text-left font-medium hover:underline"
          >
            {occurrence.task.title}
          </button>
          <p className="text-xs text-muted-foreground">
            {when}
            {rule ? ` · rule: ${ruleSummary(rule)}` : ""}
            {rule?.filters.length ? ` where ${rule.filters.map(filterLabel).join(", ")}` : ""}
          </p>
        </div>
        <span className="shrink-0 rounded-md bg-highlight px-2 py-0.5 text-xs text-primary">
          {suggestion.source === "rule" ? "Rule match" : "AI"}
        </span>
      </div>

      <ul className="m-0 list-none rounded-lg border border-border bg-field px-3 py-1">
        {events.map((e) => (
          <EventRow key={e.id} event={e} />
        ))}
      </ul>

      {mode === "reject" ? (
        <RejectPanel suggestion={suggestion} types={types} onCancel={() => setMode("idle")} />
      ) : mode === "reassign" ? (
        <ReassignPanel suggestion={suggestion} targets={targets} onCancel={() => setMode("idle")} />
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={pending}
            onClick={() => run(() => actions.accept(suggestion.id))}
            className="rounded-lg bg-primary px-3.5 py-2 font-medium text-primary-foreground disabled:opacity-60"
          >
            Accept
          </button>
          <button
            type="button"
            onClick={() => setMode("reassign")}
            className="rounded-lg border border-input px-3.5 py-2 hover:bg-accent"
          >
            Reassign
          </button>
          <button
            type="button"
            onClick={() => setMode("reject")}
            className="rounded-lg border border-input px-3.5 py-2 text-missed hover:bg-late"
          >
            Reject
          </button>
        </div>
      )}
    </article>
  );
}

function ReassignPanel({
  suggestion,
  targets,
  onCancel,
}: {
  suggestion: Suggestion;
  targets: Target[];
  onCancel: () => void;
}) {
  const { run, pending } = useAction();
  const [target, setTarget] = useState(targets[0]?.id ?? "");
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={`reassign-${suggestion.id}`} className="text-subtle">
        Move this evidence to
      </label>
      <select
        id={`reassign-${suggestion.id}`}
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        className={fieldClass}
      >
        {targets.length === 0 ? <option value="">No other occurrences this week</option> : null}
        {targets.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={pending || !target}
        onClick={() => run(() => actions.reassign(suggestion.id, target))}
        className="rounded-lg bg-primary px-3.5 py-2 font-medium text-primary-foreground disabled:opacity-60"
      >
        Move and accept
      </button>
      <button type="button" onClick={onCancel} className="px-2 py-2 text-subtle">
        Cancel
      </button>
    </div>
  );
}

const EXCLUSION_OPS: FilterOp[] = ["regex", "contains", "equals", "matches"];

function RejectPanel({
  suggestion,
  types,
  onCancel,
}: {
  suggestion: Suggestion;
  types: ConnectorType[];
  onCancel: () => void;
}) {
  const { run, pending } = useAction();
  const rule = suggestion.rule;
  const kind = types
    .find((t) => t.id === rule?.connector_type)
    ?.event_kinds.find((k) => k.name === rule?.kind);
  // Default to the title field (a commit message, a problem name): that's what people exclude by.
  const fields = [...(kind?.rule_fields ?? [])].sort(
    (a, b) => Number(b === kind?.title_field) - Number(a === kind?.title_field),
  );
  const sample = (field: string) => {
    const value = suggestion.events[0]?.payload[field];
    return String(Array.isArray(value) ? (value[0] ?? "") : (value ?? ""));
  };
  const [field, setField] = useState(fields[0] ?? "");
  const [op, setOp] = useState<FilterOp>("equals");
  const [value, setValue] = useState(() => sample(fields[0] ?? ""));

  return (
    <div className="flex flex-col gap-2.5 rounded-lg border border-border p-3">
      {rule && fields.length ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-subtle">Ignore events where</span>
          <select
            aria-label="Field"
            value={field}
            onChange={(e) => {
              setField(e.target.value);
              setValue(sample(e.target.value));
            }}
            className={fieldClass}
          >
            {fields.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
          <select
            aria-label="Operator"
            value={op}
            onChange={(e) => setOp(e.target.value as FilterOp)}
            className={fieldClass}
          >
            {EXCLUSION_OPS.map((o) => (
              <option key={o} value={o}>
                {OP_LABEL[o]}
              </option>
            ))}
          </select>
          <input
            aria-label="Value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className={cn(fieldClass, "min-w-40 flex-1 font-mono text-[13px]")}
          />
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={pending}
          onClick={() => run(() => actions.reject(suggestion.id))}
          className="rounded-lg border border-input px-3.5 py-2 text-missed hover:bg-late"
        >
          Reject
        </button>
        {rule && fields.length ? (
          <button
            type="button"
            disabled={pending || !value.trim()}
            onClick={() =>
              run(() =>
                actions.reject(suggestion.id, { field, op, value: parseFilterValue(op, value) }),
              )
            }
            className="rounded-lg border border-input px-3.5 py-2 text-missed hover:bg-late disabled:opacity-50"
          >
            Reject and ignore these
          </button>
        ) : null}
        <button type="button" onClick={onCancel} className="px-2 py-2 text-subtle">
          Cancel
        </button>
      </div>
    </div>
  );
}

function UnplannedRow({ event, targets }: { event: EventItem; targets: Target[] }) {
  const { run, pending } = useAction();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-border bg-card px-4 py-3">
      <div className="min-w-0">
        <div className="truncate">{event.title}</div>
        <div className="text-xs text-muted-foreground">
          {event.connector_name} · {time(event)}
        </div>
      </div>
      <select
        aria-label={`Attach ${event.title} to a task`}
        value=""
        disabled={pending || targets.length === 0}
        onChange={(e) => {
          if (e.target.value) run(() => actions.attachEvidence(e.target.value, [event.id]));
        }}
        className={fieldClass}
      >
        <option value="">Attach to task…</option>
        {targets.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
    </div>
  );
}
