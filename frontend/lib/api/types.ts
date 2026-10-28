// Aliases for the generated OpenAPI types. Never define API shapes by hand here.
import type { components } from "./schema";

type Schemas = components["schemas"];

export type ApiErrorBody = Schemas["ErrorResponse"];
export type Adherence = Schemas["Adherence"];
export type BacklogItem = Schemas["BacklogItem"];
export type BacklogResponse = Schemas["BacklogResponse"];
export type Occurrence = Schemas["OccurrenceRead"];
export type OccurrenceStatus = Occurrence["status"];
export type PlanItem = Schemas["PlanItem"];
export type Priority = Schemas["TaskRead"]["priority"];
export type Tally = Schemas["Tally"];
export type Task = Schemas["TaskRead"];
export type TaskCreate = Schemas["TaskCreate"];
export type TaskDetail = Schemas["TaskDetailResponse"];
export type TaskKind = Schemas["TaskRead"]["kind"];
export type TaskUpdate = Schemas["TaskUpdate"];
export type Today = Schemas["TodayResponse"];
export type Week = Schemas["WeekResponse"];
