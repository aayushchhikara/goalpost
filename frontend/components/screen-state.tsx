import { errorMessage } from "@/lib/api/errors";

export function Loading() {
  return <p className="text-sm text-muted-foreground">Loading…</p>;
}

export function LoadError({ error }: { error: unknown }) {
  return (
    <div
      role="alert"
      className="rounded-[10px] border border-border bg-card px-4 py-3.5 text-subtle"
    >
      {errorMessage(error)}
    </div>
  );
}

export function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="m-0 text-xs font-semibold tracking-[0.06em] text-muted-foreground uppercase">
      {children}
    </h2>
  );
}
