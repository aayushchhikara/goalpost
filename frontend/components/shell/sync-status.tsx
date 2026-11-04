"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { mutate } from "swr";

import { useAction } from "@/components/shell/toaster";
import { actions } from "@/lib/api/actions";
import { useStatus } from "@/lib/api/hooks";
import { clockTime, timeAgo } from "@/lib/format";

/** Sidebar footer: last and next sync, connector problems, and Sync now. */
export function SyncStatus() {
  const { data } = useStatus();
  const { run, pending } = useAction();
  const wasSyncing = useRef(false);

  // When a sync finishes, refresh every screen: it may have brought new suggestions.
  useEffect(() => {
    if (wasSyncing.current && data && !data.syncing) void mutate(() => true);
    wasSyncing.current = Boolean(data?.syncing);
  }, [data]);

  const syncing = pending || data?.syncing;
  const parts = [
    data?.last_sync_at ? `Last synced ${timeAgo(data.last_sync_at)}` : "Not synced yet",
    data?.next_sync_at ? `next at ${clockTime(data.next_sync_at)}` : null,
  ].filter(Boolean);
  const problems = data?.connector_errors ?? [];

  return (
    <div className="mt-auto flex flex-col gap-2 border-t border-border px-3 pt-4">
      <span className="text-xs text-muted-foreground" aria-live="polite">
        {syncing ? "Syncing…" : parts.join(" · ")}
      </span>
      {problems.length ? (
        <Link href="/connectors" className="text-xs text-missed hover:underline">
          {problems.length === 1
            ? `${problems[0].name}: ${problems[0].paused ? "paused" : "last sync failed"}`
            : `${problems.length} connectors need attention`}
        </Link>
      ) : null}
      <button
        type="button"
        disabled={syncing}
        onClick={() => run(() => actions.sync())}
        className="rounded-md border border-input px-2.5 py-1.5 text-left text-[13px] hover:bg-accent disabled:opacity-60"
      >
        {syncing ? "Syncing…" : "Sync now"}
      </button>
    </div>
  );
}
