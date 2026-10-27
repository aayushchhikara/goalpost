// Calendar days travel as "YYYY-MM-DD" in the user's timezone (computed by the backend).
// Build local Date objects from the parts so no timezone shift can move the day.

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export function parseDay(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function addDays(day: string, n: number): string {
  const date = parseDay(day);
  date.setDate(date.getDate() + n);
  return formatDay(date);
}

/** Monday = 0 … Sunday = 6, matching the backend. */
export function weekdayIndex(day: string): number {
  return (parseDay(day).getDay() + 6) % 7;
}

export function weekDays(monday: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
}

export function isoWeek(day: string): number {
  const date = parseDay(day);
  // The ISO week is the one containing that week's Thursday.
  date.setDate(date.getDate() + 3 - weekdayIndex(day));
  const firstThursday = new Date(date.getFullYear(), 0, 4);
  const offset = (date.getTime() - firstThursday.getTime()) / 86_400_000;
  return 1 + Math.round((offset - 3 + ((firstThursday.getDay() + 6) % 7)) / 7);
}

const month = (date: Date, style: "long" | "short") =>
  date.toLocaleDateString("en-GB", { month: style });

/** "Saturday, 24 October" */
export function longDay(day: string): string {
  const date = parseDay(day);
  const weekday = date.toLocaleDateString("en-GB", { weekday: "long" });
  return `${weekday}, ${date.getDate()} ${month(date, "long")}`;
}

/** "Sat 24" */
export function shortDay(day: string): string {
  return `${WEEKDAYS[weekdayIndex(day)]} ${parseDay(day).getDate()}`;
}

/** "19–25 Oct", or "26 Oct – 1 Nov" across a month boundary */
export function weekRange(monday: string): string {
  const start = parseDay(monday);
  const end = parseDay(addDays(monday, 6));
  if (start.getMonth() === end.getMonth()) {
    return `${start.getDate()}–${end.getDate()} ${month(end, "short")}`;
  }
  return `${start.getDate()} ${month(start, "short")} – ${end.getDate()} ${month(end, "short")}`;
}
