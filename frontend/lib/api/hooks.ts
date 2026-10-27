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
