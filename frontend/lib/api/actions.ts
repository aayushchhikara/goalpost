import { mutate } from "swr";

import { api } from "./client";
import { unwrap } from "./errors";
import type { PlanItem, TaskCreate, TaskUpdate } from "./types";

/** Every write changes several screens, so refresh everything that is loaded. */
async function write<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>) {
  const data = await unwrap(request);
  await mutate(() => true);
  return data;
}

const task = (id: string) => ({ params: { path: { task_id: id } } });
const occurrence = (id: string) => ({ params: { path: { occurrence_id: id } } });

export const actions = {
  createTask: (body: TaskCreate) => write(api.POST("/api/v1/tasks", { body })),
  updateTask: (id: string, body: TaskUpdate) =>
    write(api.PATCH("/api/v1/tasks/{task_id}", { ...task(id), body })),
  dropTask: (id: string) => write(api.POST("/api/v1/tasks/{task_id}/drop", task(id))),
  planWeek: (monday: string, items: PlanItem[]) =>
    write(
      api.POST("/api/v1/weeks/{monday}/plan", { params: { path: { monday } }, body: { items } }),
    ),
  complete: (id: string) =>
    write(api.POST("/api/v1/occurrences/{occurrence_id}/complete", occurrence(id))),
  skip: (id: string) => write(api.POST("/api/v1/occurrences/{occurrence_id}/skip", occurrence(id))),
  reopen: (id: string) =>
    write(api.POST("/api/v1/occurrences/{occurrence_id}/reopen", occurrence(id))),
  move: (id: string, date: string | null) =>
    write(api.PATCH("/api/v1/occurrences/{occurrence_id}", { ...occurrence(id), body: { date } })),
};
