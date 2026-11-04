"use client";

import { useState, type FormEvent } from "react";

import { Field, fieldClass } from "@/components/fields";
import { LoadError, Loading, SectionHeading } from "@/components/screen-state";
import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import { useConnectorTypes, useConnectors, useStatus, useSyncRuns } from "@/lib/api/hooks";
import type { Connector, ConnectorType, SyncRun } from "@/lib/api/types";
import { timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ConnectorsScreen() {
  const connectors = useConnectors();
  const types = useConnectorTypes();
  const runs = useSyncRuns(10);
  useStatus(); // polls while a sync runs; the sidebar refreshes everything when it ends

  const error = connectors.error ?? types.error;
  if (error) return <LoadError error={error} />;
  if (!connectors.data || !types.data) return <Loading />;

  const typeById = new Map(types.data.items.map((t) => [t.id, t]));
  const names = new Map(connectors.data.items.map((c) => [c.id, c.name]));

  return (
    <section aria-labelledby="connectors-h" className="flex w-full max-w-3xl flex-col gap-6">
      <header>
        <h1 id="connectors-h" className="m-0 text-[26px] font-semibold tracking-[-0.02em]">
          Connectors
        </h1>
        <p className="mt-0.5 text-muted-foreground">
          Activity from these services becomes suggested proof. Syncs run on startup, every 4 hours,
          and when you press Sync now.
        </p>
      </header>

      {types.data.load_errors.map((p) => (
        <p
          key={p.folder}
          role="alert"
          className="rounded-[10px] border border-border bg-late px-4 py-3 text-missed"
        >
          The {p.folder} connector couldn&apos;t load: {p.message}
        </p>
      ))}

      <div className="flex flex-col gap-3">
        {connectors.data.items.length === 0 ? (
          <p className="text-subtle">No connectors yet. Add one below.</p>
        ) : null}
        {connectors.data.items.map((c) => (
          <ConnectorCard key={c.id} connector={c} type={typeById.get(c.type)} />
        ))}
      </div>

      <AddConnector types={types.data.items} />

      {runs.data?.items.length ? (
        <div className="flex flex-col gap-2">
          <SectionHeading>Recent syncs</SectionHeading>
          {runs.data.items.map((r) => (
            <RunRow key={r.id} run={r} name={names.get(r.connector_id) ?? "Removed connector"} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

const STATUS_STYLE: Record<Connector["status"], [string, string]> = {
  ok: ["Working", "text-success"],
  syncing: ["Syncing…", "text-primary"],
  never_synced: ["Not synced yet", "text-muted-foreground"],
  failing: ["Last sync failed", "text-missed"],
  paused: ["Paused", "text-missed"],
  disabled: ["Disabled", "text-muted-foreground"],
};

function configSummary(config: Record<string, unknown>): string {
  return Object.entries(config)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
    .join(" · ");
}

function ConnectorCard({ connector, type }: { connector: Connector; type?: ConnectorType }) {
  const { run, pending } = useAction();
  const [editing, setEditing] = useState(false);
  const [test, setTest] = useState<{ ok: boolean; message: string } | null>(null);
  const [label, color] = STATUS_STYLE[connector.status];
  const last = connector.last_run;
  const missing = (type?.secrets ?? []).filter((s) => !s.present);

  return (
    <article className="flex flex-col gap-3 rounded-[10px] border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-medium">
            {connector.name}
            {type && type.name !== connector.name ? (
              <span className="ml-2 text-xs text-muted-foreground">{type.name}</span>
            ) : null}
          </div>
          <div className="text-xs text-muted-foreground">{configSummary(connector.config)}</div>
        </div>
        <span className={cn("text-xs font-medium", color)}>{label}</span>
      </div>

      <div className="text-[13px] text-subtle">
        {connector.pause_reason ? (
          <p className="text-missed">
            Paused: {connector.pause_reason}. Fix it, then Test or Sync now to resume.
          </p>
        ) : last?.status === "failed" ? (
          <p className="text-missed">Last sync failed: {last.error}</p>
        ) : null}
        <p>
          {connector.last_success_at
            ? `Last synced ${timeAgo(connector.last_success_at)}`
            : "Never synced successfully"}
          {last?.finished_at && last.status !== "failed"
            ? ` · ${last.events_added} new event${last.events_added === 1 ? "" : "s"} last time`
            : ""}
        </p>
        {missing.length ? (
          <p className="text-missed">Missing in .env: {missing.map((s) => s.name).join(", ")}</p>
        ) : null}
      </div>

      {test ? (
        <p role="status" className={cn("text-[13px]", test.ok ? "text-success" : "text-missed")}>
          {test.ok ? "✓ " : "✗ "}
          {test.message}
        </p>
      ) : null}

      {editing && type ? (
        <EditConnector connector={connector} type={type} onDone={() => setEditing(false)} />
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={pending}
            onClick={async () =>
              setTest((await run(() => actions.testConnector(connector.id))) ?? null)
            }
            className="rounded-lg border border-input px-3 py-1.5 hover:bg-accent"
          >
            Test
          </button>
          <button
            type="button"
            disabled={pending || !connector.enabled || connector.status === "syncing"}
            onClick={() => run(() => actions.sync(connector.id))}
            className="rounded-lg border border-input px-3 py-1.5 hover:bg-accent disabled:opacity-50"
          >
            Sync now
          </button>
          <button
            type="button"
            disabled={!type}
            onClick={() => setEditing(true)}
            className="rounded-lg border border-input px-3 py-1.5 hover:bg-accent"
          >
            Edit
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() =>
              run(() => actions.updateConnector(connector.id, { enabled: !connector.enabled }))
            }
            className="rounded-lg border border-input px-3 py-1.5 text-subtle hover:bg-accent"
          >
            {connector.enabled ? "Disable" : "Enable"}
          </button>
        </div>
      )}
    </article>
  );
}

function RunRow({ run, name }: { run: SyncRun; name: string }) {
  const tone =
    run.status === "failed"
      ? "text-missed"
      : run.status === "partial"
        ? "text-primary"
        : "text-success";
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-3 text-[13px]">
      <span>
        {name} <span className="text-muted-foreground">· {run.trigger}</span>
      </span>
      <span className="text-muted-foreground">
        <span className={tone}>{run.status ?? "running"}</span>
        {run.status && run.status !== "failed" ? ` · +${run.events_added}` : ""}
        {run.error ? ` · ${run.error}` : ""} · {timeAgo(run.started_at)}
      </span>
    </div>
  );
}

// Setup forms are generated from each connector's config JSON Schema.

type SchemaField = {
  type?: string;
  title?: string;
  description?: string;
  items?: { type?: string };
};
type Schema = { properties?: Record<string, SchemaField>; required?: string[] };

function toForm(schema: Schema, config: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(schema.properties ?? {}).map(([key, field]) => {
      const value = config[key];
      if (field.type === "array") return [key, Array.isArray(value) ? value.join("\n") : ""];
      return [key, value === undefined || value === null ? "" : String(value)];
    }),
  );
}

function fromForm(schema: Schema, values: Record<string, string>): Record<string, unknown> {
  const config: Record<string, unknown> = {};
  for (const [key, field] of Object.entries(schema.properties ?? {})) {
    const raw = (values[key] ?? "").trim();
    if (field.type === "array") {
      config[key] = raw
        .split(/[\n,]/)
        .map((v) => v.trim())
        .filter(Boolean);
    } else if (field.type === "integer" || field.type === "number") {
      if (raw) config[key] = Number(raw);
    } else if (field.type === "boolean") {
      config[key] = raw === "true";
    } else if (raw || (schema.required ?? []).includes(key)) {
      config[key] = raw;
    }
  }
  return config;
}

function ConfigFields({
  schema,
  values,
  onChange,
  idPrefix,
}: {
  schema: Schema;
  values: Record<string, string>;
  onChange: (values: Record<string, string>) => void;
  idPrefix: string;
}) {
  return (
    <>
      {Object.entries(schema.properties ?? {}).map(([key, field]) => {
        const id = `${idPrefix}-${key}`;
        const label = `${field.title ?? key}${field.type === "array" ? " (one per line)" : ""}`;
        const common = {
          id,
          value: values[key] ?? "",
          placeholder: field.description,
          className: cn(fieldClass, "w-full"),
        };
        return (
          <Field key={key} label={label} htmlFor={id}>
            {field.type === "array" ? (
              <textarea
                {...common}
                rows={3}
                onChange={(e) => onChange({ ...values, [key]: e.target.value })}
              />
            ) : (
              <input
                {...common}
                type={field.type === "integer" || field.type === "number" ? "number" : "text"}
                onChange={(e) => onChange({ ...values, [key]: e.target.value })}
              />
            )}
          </Field>
        );
      })}
    </>
  );
}

function SecretsNote({ type }: { type: ConnectorType }) {
  if (type.secrets.length === 0)
    return <p className="text-xs text-muted-foreground">No login needed.</p>;
  return (
    <ul className="m-0 flex list-none flex-col gap-1 p-0 text-xs">
      {type.secrets.map((s) => (
        <li key={s.name} className={s.present ? "text-success" : "text-missed"}>
          {s.present ? "✓" : "✗"} <code className="font-mono">{s.name}</code>{" "}
          {s.present ? "is set in .env" : "is missing: add it to .env and restart the backend"}
        </li>
      ))}
      <li className="text-muted-foreground">Secrets stay in .env; Goalpost never stores them.</li>
    </ul>
  );
}

function AddConnector({ types }: { types: ConnectorType[] }) {
  const { run, pending } = useAction();
  const [typeId, setTypeId] = useState(types[0]?.id ?? "");
  const type = types.find((t) => t.id === typeId) ?? types[0];
  const schema = (type?.config_schema ?? {}) as Schema;
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  if (!type) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    const created = await run(() =>
      actions.createConnector({
        type: type.id,
        name: name.trim() || null,
        config: fromForm(schema, values),
      }),
    );
    if (!created) return;
    setName("");
    setValues({});
    // Check it right away so problems show up before the first sync.
    setResult((await run(() => actions.testConnector(created.id))) ?? null);
  }

  return (
    <form
      onSubmit={submit}
      aria-label="Add connector"
      className="flex flex-col gap-3.5 rounded-[10px] border border-dashed border-input p-4"
    >
      <SectionHeading>Add a connector</SectionHeading>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Service" htmlFor="new-type">
          <select
            id="new-type"
            value={type.id}
            onChange={(e) => {
              setTypeId(e.target.value);
              setValues({});
              setResult(null);
            }}
            className={fieldClass}
          >
            {types.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Name (optional)" htmlFor="new-name">
          <input
            id="new-name"
            value={name}
            placeholder={type.name}
            onChange={(e) => setName(e.target.value)}
            className={fieldClass}
          />
        </Field>
      </div>
      <p className="text-[13px] text-subtle">{type.description}</p>
      <ConfigFields schema={schema} values={values} onChange={setValues} idPrefix="new" />
      <SecretsNote type={type} />
      {result ? (
        <p role="status" className={cn("text-[13px]", result.ok ? "text-success" : "text-missed")}>
          Added. {result.ok ? "✓" : "✗"} {result.message}
        </p>
      ) : null}
      <div>
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-primary px-3.5 py-2 font-medium text-primary-foreground disabled:opacity-60"
        >
          Add {type.name}
        </button>
      </div>
    </form>
  );
}

function EditConnector({
  connector,
  type,
  onDone,
}: {
  connector: Connector;
  type: ConnectorType;
  onDone: () => void;
}) {
  const { run, pending } = useAction();
  const schema = type.config_schema as Schema;
  const [name, setName] = useState(connector.name);
  const [values, setValues] = useState(() => toForm(schema, connector.config));
  const [secretRef, setSecretRef] = useState(connector.secret_ref ?? "");

  async function save(event: FormEvent) {
    event.preventDefault();
    const saved = await run(() =>
      actions.updateConnector(connector.id, {
        name,
        config: fromForm(schema, values),
        ...(type.secrets.length ? { secret_ref: secretRef } : {}),
      }),
    );
    if (saved) onDone();
  }

  return (
    <form onSubmit={save} aria-label={`Edit ${connector.name}`} className="flex flex-col gap-3">
      <Field label="Name" htmlFor={`edit-${connector.id}-name`}>
        <input
          id={`edit-${connector.id}-name`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={fieldClass}
        />
      </Field>
      <ConfigFields
        schema={schema}
        values={values}
        onChange={setValues}
        idPrefix={`edit-${connector.id}`}
      />
      {type.secrets.length ? (
        <Field
          label={`.env key for the secret (default ${type.secrets[0].name})`}
          htmlFor={`edit-${connector.id}-ref`}
        >
          <input
            id={`edit-${connector.id}-ref`}
            value={secretRef}
            placeholder={type.secrets[0].name}
            onChange={(e) => setSecretRef(e.target.value)}
            className={cn(fieldClass, "font-mono")}
          />
        </Field>
      ) : null}
      <p className="text-xs text-muted-foreground">
        Changing the settings starts the sync cursor over; already-synced events stay.
      </p>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-primary px-3.5 py-1.5 font-medium text-primary-foreground disabled:opacity-60"
        >
          Save
        </button>
        <button type="button" onClick={onDone} className="px-2 text-subtle">
          Cancel
        </button>
      </div>
    </form>
  );
}
