"use client";

import { useState } from "react";

import { fieldClass } from "@/components/fields";
import { SectionHeading } from "@/components/screen-state";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import { useConnectorTypes, useConnectors } from "@/lib/api/hooks";
import type { EventItem, Filter, FilterOp, Rule } from "@/lib/api/types";
import { shortDay } from "@/lib/dates";
import { OP_LABEL, filterLabel, parseFilterValue, ruleSummary } from "@/lib/rules";
import { cn } from "@/lib/utils";

const OPS = Object.keys(OP_LABEL) as FilterOp[];

type Row = { field: string; op: FilterOp; value: string };

const toRow = (f: Filter): Row => ({
  field: f.field,
  op: f.op,
  value: Array.isArray(f.value) ? f.value.join(", ") : String(f.value),
});

/** The task's completion rule: shown as a summary, edited in place. */
export function RuleSection({ taskId, rule }: { taskId: string; rule: Rule | null }) {
  const [editing, setEditing] = useState(false);
  const { run, pending } = useAction();

  return (
    <section
      aria-labelledby="rule-h"
      className="flex flex-col gap-2 rounded-[10px] border border-border bg-field px-4 py-3.5"
    >
      <div className="flex items-baseline justify-between">
        <SectionHeading>
          <span id="rule-h">Completion rule</span>
        </SectionHeading>
        {!editing ? (
          <div className="flex gap-1.5">
            <button
              type="button"
              onClick={() => setEditing(true)}
              className="rounded-md border border-input px-2 py-0.5 text-xs hover:bg-accent"
            >
              {rule ? "Edit" : "Add rule"}
            </button>
            {rule ? (
              <button
                type="button"
                disabled={pending}
                onClick={() => run(() => actions.deleteRule(taskId))}
                className="rounded-md border border-input px-2 py-0.5 text-xs text-missed hover:bg-late"
              >
                Remove
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {editing ? (
        <RuleForm taskId={taskId} rule={rule} onDone={() => setEditing(false)} />
      ) : rule ? (
        <RuleView taskId={taskId} rule={rule} />
      ) : (
        <p className="text-subtle">
          No rule: mark it done by hand, or add a rule so synced activity is suggested as proof.
        </p>
      )}
    </section>
  );
}

function RuleView({ taskId, rule }: { taskId: string; rule: Rule }) {
  const { run, pending } = useAction();
  return (
    <>
      <div>
        At least <span className="font-mono">{rule.min_count}</span> {rule.kind} from{" "}
        <strong className="font-semibold">{rule.connector_name ?? "a removed connector"}</strong>
      </div>
      {rule.filters.length || rule.exclusions.length ? (
        <div className="flex flex-wrap gap-1.5 font-mono text-xs">
          {rule.filters.map((f, i) => (
            <span key={i} className="rounded-md bg-accent px-2 py-0.5">
              {filterLabel(f)}
            </span>
          ))}
          {rule.exclusions.map((x) => (
            <span
              key={x.id}
              className="flex items-center gap-1 rounded-md bg-late px-2 py-0.5 text-missed"
            >
              not {filterLabel(x.filter)}
              <button
                type="button"
                aria-label={`Remove exclusion ${filterLabel(x.filter)}`}
                disabled={pending}
                onClick={() => run(() => actions.deleteExclusion(taskId, x.id))}
                className="ml-0.5 hover:text-foreground"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
      {rule.exclusions.some((x) => x.created_from_suggestion_id) ? (
        <span className="text-xs text-muted-foreground">
          Exclusions were added when you rejected suggestions (
          {rule.exclusions
            .map((x) => shortDay(x.created_at.slice(0, 10)))
            .filter((d, i, all) => all.indexOf(d) === i)
            .join(", ")}
          ).
        </span>
      ) : null}
    </>
  );
}

function RuleForm({
  taskId,
  rule,
  onDone,
}: {
  taskId: string;
  rule: Rule | null;
  onDone: () => void;
}) {
  const connectors = useConnectors();
  const types = useConnectorTypes();
  const { run, pending } = useAction();
  const instances = connectors.data?.items ?? [];

  // Nothing chosen yet means the first connector; the list may still be loading on first render.
  const [chosenId, setConnectorId] = useState(rule?.connector_id ?? "");
  const connectorId = chosenId || instances[0]?.id || "";
  const connector = instances.find((c) => c.id === connectorId);
  const type = types.data?.items.find((t) => t.id === connector?.type);
  const [kind, setKind] = useState(rule?.kind ?? type?.event_kinds[0]?.name ?? "");
  const eventKind = type?.event_kinds.find((k) => k.name === kind) ?? type?.event_kinds[0];
  const fields = eventKind?.rule_fields ?? [];
  const [rows, setRows] = useState<Row[]>(rule?.filters.map(toRow) ?? []);
  const [minCount, setMinCount] = useState(rule?.min_count ?? 1);

  if (connectors.isLoading || types.isLoading) {
    return <p className="text-subtle">Loading connectors…</p>;
  }
  if (instances.length === 0) {
    return (
      <div className="flex items-center justify-between gap-3 text-subtle">
        <span>Add a connector first, then rules can read its activity.</span>
        <button type="button" onClick={onDone} className="text-xs underline">
          Close
        </button>
      </div>
    );
  }

  const update = (i: number, patch: Partial<Row>) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  async function save() {
    const saved = await run(() =>
      actions.setRule(taskId, {
        connector_id: connectorId,
        kind: eventKind?.name ?? kind,
        min_count: minCount,
        filters: rows
          .filter((r) => r.value.trim())
          .map((r) => ({ field: r.field, op: r.op, value: parseFilterValue(r.op, r.value) })),
      }),
    );
    if (saved) onDone();
  }

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-subtle">At least</span>
        <input
          aria-label="Minimum count"
          type="number"
          min={1}
          max={100}
          value={minCount}
          onChange={(e) => setMinCount(Math.max(1, Number(e.target.value) || 1))}
          className={cn(fieldClass, "w-16 font-mono")}
        />
        <select
          aria-label="Event kind"
          value={eventKind?.name ?? ""}
          onChange={(e) => setKind(e.target.value)}
          className={fieldClass}
        >
          {type?.event_kinds.map((k) => (
            <option key={k.name} value={k.name}>
              {k.name}
            </option>
          ))}
        </select>
        <span className="text-subtle">from</span>
        <select
          aria-label="Connector"
          value={connectorId}
          onChange={(e) => {
            setConnectorId(e.target.value);
            setRows([]); // fields differ between connectors
            setKind("");
          }}
          className={fieldClass}
        >
          {instances.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-10 shrink-0 text-right text-subtle">{i === 0 ? "where" : "and"}</span>
          <select
            aria-label="Field"
            value={row.field}
            onChange={(e) => update(i, { field: e.target.value })}
            className={fieldClass}
          >
            {fields.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
          <select
            aria-label="Operator"
            value={row.op}
            onChange={(e) => update(i, { op: e.target.value as FilterOp })}
            className={fieldClass}
          >
            {OPS.map((o) => (
              <option key={o} value={o}>
                {OP_LABEL[o]}
              </option>
            ))}
          </select>
          <input
            aria-label="Value"
            value={row.value}
            placeholder={row.op === "one_of" ? "a, b, c" : row.op === "matches" ? "backend/*" : ""}
            onChange={(e) => update(i, { value: e.target.value })}
            className={cn(fieldClass, "w-0 min-w-0 flex-1 font-mono text-[13px]")}
          />
          <button
            type="button"
            aria-label="Remove filter"
            onClick={() => setRows(rows.filter((_, j) => j !== i))}
            className="shrink-0 px-1 text-subtle hover:text-foreground"
          >
            ×
          </button>
        </div>
      ))}

      <div className="flex flex-wrap gap-2">
        {fields.length ? (
          <button
            type="button"
            onClick={() => setRows([...rows, { field: fields[0], op: "equals", value: "" }])}
            className="rounded-md border border-dashed border-ring px-2.5 py-1 text-xs text-subtle hover:text-foreground"
          >
            Add filter
          </button>
        ) : null}
        <span className="flex-1" />
        <button type="button" onClick={onDone} className="px-2 text-subtle">
          Cancel
        </button>
        <button
          type="button"
          disabled={pending || !connectorId}
          onClick={save}
          className="rounded-lg bg-primary px-3.5 py-1.5 font-medium text-primary-foreground disabled:opacity-60"
        >
          Save rule
        </button>
      </div>
      {rule ? <p className="text-xs text-muted-foreground">Current: {ruleSummary(rule)}</p> : null}
    </div>
  );
}

export function EvidenceSection({ evidence }: { evidence: EventItem[] }) {
  return (
    <section aria-labelledby="ev-h" className="flex flex-col gap-1.5">
      <SectionHeading>
        <span id="ev-h">Evidence</span>
      </SectionHeading>
      {evidence.length === 0 ? (
        <p className="text-subtle">None yet on this week&apos;s occurrence.</p>
      ) : (
        evidence.map((e) => (
          <div key={e.id} className="flex items-baseline justify-between gap-3 text-[13px]">
            <span className="min-w-0 truncate">
              {e.url ? (
                <a href={e.url} target="_blank" rel="noreferrer" className="hover:underline">
                  {e.title}
                </a>
              ) : (
                e.title
              )}
            </span>
            <span className="shrink-0 text-xs text-muted-foreground">
              {e.connector_name} · {shortDay(e.local_date)}
            </span>
          </div>
        ))
      )}
    </section>
  );
}
