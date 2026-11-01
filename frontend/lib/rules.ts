import type { Filter, FilterOp, Rule } from "./api/types";

export const OP_LABEL: Record<FilterOp, string> = {
  equals: "is",
  one_of: "is one of",
  contains: "contains",
  matches: "matches (glob)",
  regex: "matches (regex)",
  at_least: "at least",
  at_most: "at most",
};

const OP_SYMBOL: Record<FilterOp, string> = {
  equals: "=",
  one_of: "in",
  contains: "contains",
  matches: "~",
  regex: "~",
  at_least: "≥",
  at_most: "≤",
};

/** "repo = goalpost", "path ~ backend/auth/*", "repo in goalpost, dotfiles" */
export function filterLabel(filter: Filter): string {
  const value = Array.isArray(filter.value) ? filter.value.join(", ") : String(filter.value);
  return `${filter.field} ${OP_SYMBOL[filter.op]} ${value}`;
}

/** "≥1 commit from Personal GitHub" */
export function ruleSummary(rule: Rule): string {
  const source = rule.connector_name ?? "a removed connector";
  return `≥${rule.min_count} ${rule.kind} from ${source}`;
}

/** Parse what a user typed into a filter value: lists split on commas, numbers for bounds. */
export function parseFilterValue(op: FilterOp, raw: string): Filter["value"] {
  if (op === "one_of") {
    return raw
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
  }
  if (op === "at_least" || op === "at_most") return Number(raw);
  return raw;
}
