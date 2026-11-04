import useSWR from "swr";

import { api } from "./client";
import { unwrap } from "./errors";
import type { Priority } from "./types";

export function useToday() {
  return useSWR("today", () => unwrap(api.GET("/api/v1/today")));
}

export function useWeek(monday: string | undefined) {
  return useSWR(monday ? (["week", monday] as const) : null, ([, m]) =>
    unwrap(api.GET("/api/v1/weeks/{monday}", { params: { path: { monday: m } } })),
  );
}

export function useBacklog(priority?: Priority) {
  return useSWR(["backlog", priority ?? "all"] as const, () =>
    unwrap(api.GET("/api/v1/backlog", { params: { query: { priority } } })),
  );
}

export function useTask(taskId: string | null) {
  return useSWR(taskId ? (["task", taskId] as const) : null, ([, id]) =>
    unwrap(api.GET("/api/v1/tasks/{task_id}", { params: { path: { task_id: id } } })),
  );
}

export function useSuggestions() {
  return useSWR("suggestions", () =>
    unwrap(api.GET("/api/v1/suggestions", { params: { query: { status: "pending" } } })),
  );
}

export function useUnplanned(monday: string | undefined) {
  return useSWR(monday ? (["unplanned", monday] as const) : null, ([, week]) =>
    unwrap(api.GET("/api/v1/events/unplanned", { params: { query: { week } } })),
  );
}

/** Polls every 2 s while a sync runs, so the sidebar and Connectors page show it finishing. */
export function useStatus() {
  return useSWR("status", () => unwrap(api.GET("/api/v1/status")), {
    refreshInterval: (data) => (data?.syncing ? 2000 : 60000),
  });
}

export function useSyncRuns(limit = 20) {
  return useSWR(["sync-runs", limit] as const, () =>
    unwrap(api.GET("/api/v1/sync/runs", { params: { query: { limit } } })),
  );
}

export function useConnectors() {
  return useSWR("connectors", () => unwrap(api.GET("/api/v1/connectors")));
}

export function useConnectorTypes() {
  return useSWR("connector-types", () => unwrap(api.GET("/api/v1/connector-types")));
}
