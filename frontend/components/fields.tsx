import type { ReactNode } from "react";

import { WEEKDAYS } from "@/lib/dates";
import { cn } from "@/lib/utils";

export const fieldClass =
  "rounded-lg border border-input bg-field px-2.5 py-2 text-foreground outline-none focus-visible:border-ring";

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-xs text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

/** Weekday toggles, Monday = 0 … Sunday = 6. */
export function DayPicker({
  value,
  onChange,
  label = "Recurring days",
}: {
  value: number[];
  onChange: (days: number[]) => void;
  label?: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {WEEKDAYS.map((name, day) => {
        const on = value.includes(day);
        return (
          <button
            key={name}
            type="button"
            aria-pressed={on}
            onClick={() =>
              onChange(on ? value.filter((d) => d !== day) : [...value, day].sort((a, b) => a - b))
            }
            className={cn(
              "min-w-11 rounded-md border px-2 py-1 text-xs",
              on
                ? "border-primary bg-highlight text-primary"
                : "border-input text-subtle hover:text-foreground",
            )}
          >
            {name}
          </button>
        );
      })}
    </div>
  );
}
