import type { CardConfig, HomeworkItem, PeriodProgress, ProgressPeriod } from "./types";

/** The progress steps of the card (PM decision). */
export const STEPS = [0, 25, 50, 75, 100] as const;

export const DEFAULT_DAYS_AHEAD = 7;
export const MAX_DAYS_AHEAD = 365;

/** The nearest step (a tie rounds up); values outside 0-100 are clamped. */
export function snapToStep(progress: number): number {
  if (!Number.isFinite(progress)) return 0;
  const clamped = Math.min(Math.max(progress, 0), 100);
  return Math.min(Math.round(clamped / 25) * 25, 100);
}

/** The progress to send when an item is ticked (100) or unticked (its last_partial). */
export function toggleTarget(item: HomeworkItem): number {
  if (!item.completed) return 100;
  const restore = Math.round(item.last_partial);
  return Math.min(Math.max(Number.isFinite(restore) ? restore : 0, 0), 99);
}

// -- dates: plain YYYY-MM-DD strings, so the browser's time zone never shifts a day --

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

function utcDate(iso: string): Date {
  const match = ISO_DATE.exec(iso);
  if (!match) return new Date(NaN);
  return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
}

export function addDays(iso: string, days: number): string {
  const date = utcDate(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** Today as YYYY-MM-DD in the given IANA time zone (the browser's zone when omitted). */
export function todayIso(now: Date, timeZone?: string): string {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now);
    if (ISO_DATE.test(parts)) return parts;
  } catch {
    // an unknown time zone: use the browser's
  }
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

/** "maandag 16 november" / "Monday, 16 November" */
export function formatDay(iso: string, language: string): string {
  const date = utcDate(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(language, {
    timeZone: "UTC",
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}

// -- filtering and grouping --

export interface FilterOptions {
  showCompleted: boolean;
  showPast: boolean;
  daysAhead: number;
  /** YYYY-MM-DD */
  today: string;
  /** Completed items that stay visible anyway (ticked in this session, so they can be unticked). */
  keep?: ReadonlySet<string>;
}

/**
 * Completed items only with show_completed, past days only with show_past, and nothing
 * later than `daysAhead` days after today (that day included). Completed items in `keep`
 * stay, so an item that was just ticked off does not vanish under the finger.
 */
export function filterItems(
  items: readonly HomeworkItem[],
  options: FilterOptions,
): HomeworkItem[] {
  const last = addDays(options.today, options.daysAhead);
  return items.filter((item) => {
    if (item.completed && !options.showCompleted && !options.keep?.has(item.uid)) return false;
    if (item.date < options.today) return options.showPast;
    return item.date <= last;
  });
}

export type DayKind = "past" | "today" | "tomorrow" | "future";

export interface DayGroup {
  date: string;
  kind: DayKind;
  items: HomeworkItem[];
}

function kindOf(date: string, today: string): DayKind {
  if (date < today) return "past";
  if (date === today) return "today";
  if (date === addDays(today, 1)) return "tomorrow";
  return "future";
}

/** Items per day, days in date order (past days first); items keep their order. */
export function groupByDay(
  items: readonly HomeworkItem[],
  today: string,
): DayGroup[] {
  const groups = new Map<string, DayGroup>();
  for (const item of items) {
    let group = groups.get(item.date);
    if (!group) {
      group = { date: item.date, kind: kindOf(item.date, today), items: [] };
      groups.set(item.date, group);
    }
    group.items.push(item);
  }
  return [...groups.values()].sort((a, b) => a.date.localeCompare(b.date));
}

// -- optimistic updates --

export interface Overlay {
  progress: number;
  completed: boolean;
  /** What unticking restores, kept in step with the optimistic progress. */
  last_partial: number;
}

/**
 * The optimistic state after setting `progress` on an item as shown now. It mirrors the
 * backend: below 100 the value itself is the last partial; reaching 100 keeps the value
 * from before (so tick, untick restores it even while requests are still in flight).
 */
export function optimisticOverlay(item: HomeworkItem, progress: number): Overlay {
  let lastPartial = item.last_partial;
  if (progress < 100) lastPartial = progress;
  else if (item.progress < 100) lastPartial = item.progress;
  return { progress, completed: progress >= 100, last_partial: lastPartial };
}

/** The items with the optimistic (not yet confirmed) progress applied. */
export function applyOverlay(
  items: readonly HomeworkItem[],
  overlay: ReadonlyMap<string, Overlay>,
): HomeworkItem[] {
  if (overlay.size === 0) return [...items];
  return items.map((item) => {
    const change = overlay.get(item.uid);
    return change ? { ...item, ...change } : item;
  });
}

// -- config --

export interface NormalizedConfig {
  entity: string;
  show_completed: boolean;
  show_past: boolean;
  days_ahead: number;
  show_progress_tomorrow: boolean;
  show_progress_week: boolean;
  show_progress_next_week: boolean;
  title: string;
}

/** The progress periods, in display order, with the config option that shows each. */
export const PROGRESS_PERIODS = [
  { period: "tomorrow", option: "show_progress_tomorrow" },
  { period: "week", option: "show_progress_week" },
  { period: "next_week", option: "show_progress_next_week" },
] as const satisfies readonly { period: ProgressPeriod; option: keyof NormalizedConfig }[];

/** The value of a bar as a whole percentage within 0-100. */
export function barPercent(progress: PeriodProgress): number {
  const value = Number.isFinite(progress.value) ? progress.value : 0;
  return Math.min(Math.max(Math.round(value), 0), 100);
}

/** Validate a card config and fill in the defaults. An empty entity is allowed (the card then asks for one). */
export function normalizeConfig(config: Partial<CardConfig> | undefined): NormalizedConfig {
  if (!config || typeof config !== "object") {
    throw new Error("Invalid configuration");
  }
  const entity = config.entity ?? "";
  if (typeof entity !== "string") {
    throw new Error("entity must be a to-do entity id");
  }
  if (entity !== "" && !entity.startsWith("todo.")) {
    throw new Error("entity must be a to-do entity (todo.*)");
  }
  const raw = config.days_ahead ?? DEFAULT_DAYS_AHEAD;
  if (typeof raw !== "number" || !Number.isFinite(raw) || raw < 0) {
    throw new Error("days_ahead must be a number of days (0 or more)");
  }
  return {
    entity,
    show_completed: config.show_completed === true,
    show_past: config.show_past === true,
    days_ahead: Math.min(Math.floor(raw), MAX_DAYS_AHEAD),
    show_progress_tomorrow: config.show_progress_tomorrow === true,
    show_progress_week: config.show_progress_week === true,
    show_progress_next_week: config.show_progress_next_week === true,
    title: typeof config.title === "string" ? config.title : "",
  };
}
