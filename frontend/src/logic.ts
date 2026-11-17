import type {
  Appointment,
  CardConfig,
  CardLanguage,
  HomeworkItem,
  HomeworkPayload,
  ItemOverride,
  LabelOption,
  PeriodProgress,
  ProgressPeriod,
  Proposal,
  Subtask,
} from "./types";

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
export function toggleTarget(item: Pick<HomeworkItem, "completed" | "last_partial">): number {
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
export function optimisticOverlay(
  item: Pick<HomeworkItem, "progress" | "last_partial">,
  progress: number,
): Overlay {
  let lastPartial = item.last_partial;
  if (progress < 100) lastPartial = progress;
  else if (item.progress < 100) lastPartial = item.progress;
  return { progress, completed: progress >= 100, last_partial: lastPartial };
}

/** The mean of the subtasks' progress, rounded half up (the backend's derived progress). */
export function derivedProgress(subtasks: readonly Pick<Subtask, "progress">[]): number {
  if (subtasks.length === 0) return 0;
  const total = subtasks.reduce((sum, subtask) => sum + subtask.progress, 0);
  return Math.min(Math.max(Math.floor(total / subtasks.length + 0.5), 0), 100);
}

/** The item has subtasks that count (a disabled item hides them). */
export function isDerived(item: HomeworkItem): boolean {
  return item.derived === true && item.disabled !== true && (item.subtasks?.length ?? 0) > 0;
}

/**
 * The item with another list of subtasks; its progress follows. When the last subtask is
 * deleted the item shows the derived value of no subtasks (0) until the push brings back its own.
 */
function withSubtasks(item: HomeworkItem, subtasks: Subtask[]): HomeworkItem {
  if (subtasks.length === 0) return { ...item, subtasks, derived: false };
  const progress = derivedProgress(subtasks);
  return { ...item, subtasks, derived: true, progress, completed: progress >= 100 };
}

/** The items with the optimistic (not yet confirmed) progress applied, to items and subtasks. */
export function applyOverlay(
  items: readonly HomeworkItem[],
  overlay: ReadonlyMap<string, Overlay>,
): HomeworkItem[] {
  if (overlay.size === 0) return [...items];
  return items.map((item) => {
    const subtasks = item.subtasks;
    if (subtasks?.some((subtask) => overlay.has(subtask.uid))) {
      return withSubtasks(
        item,
        subtasks.map((subtask) => {
          const change = overlay.get(subtask.uid);
          return change ? { ...subtask, ...change } : subtask;
        }),
      );
    }
    const change = overlay.get(item.uid);
    return change ? { ...item, ...change } : item;
  });
}

// -- subtasks --

/** An optimistic change of a subtask (not yet confirmed): a new title and/or date, or a deletion. */
export interface SubtaskEdit {
  title?: string;
  planned?: string;
  /** A number sets the estimate, null clears it, undefined leaves it. */
  minutes?: number | null;
  deleted?: boolean;
}

/** The estimates the forms offer (minutes). */
export const MINUTE_CHOICES: readonly number[] = [15, 30, 45, 60, 90, 120, 180, 240];

/** The choices plus existing values (form and stored) that are not among them, in ascending order. */
export function minuteChoices(...existing: (number | null | undefined)[]): number[] {
  const extra = existing.filter(
    (value, index): value is number =>
      typeof value === "number" && !MINUTE_CHOICES.includes(value) && existing.indexOf(value) === index,
  );
  return [...MINUTE_CHOICES, ...extra].sort((a, b) => a - b);
}

/** "45 min", "1 u", "1 u 15 min" (nl) / "1 h 15 min" (en). */
export function formatMinutes(minutes: number, language: string): string {
  const hour = language === "nl" ? "u" : "h";
  const whole = Math.max(0, Math.round(minutes));
  const hours = Math.floor(whole / 60);
  const rest = whole % 60;
  if (hours === 0) return `${rest} min`;
  return rest === 0 ? `${hours} ${hour}` : `${hours} ${hour} ${rest} min`;
}

/**
 * The planned minutes per day: the estimates of all subtasks (done or not) by their current
 * date, over the items that are not disabled. Like `planned_minutes` of the coach's get_overview.
 */
export function plannedMinutes(items: readonly HomeworkItem[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const item of items) {
    if (item.disabled === true) continue;
    for (const subtask of item.subtasks ?? []) {
      if (typeof subtask.minutes !== "number") continue;
      totals.set(subtask.date, (totals.get(subtask.date) ?? 0) + subtask.minutes);
    }
  }
  return totals;
}

/** "1 u 30" / "45 min": minutes without the trailing "min" after hours, for lists of days. */
export function formatMinutesShort(minutes: number, language: string): string {
  const text = formatMinutes(minutes, language);
  return Math.round(minutes) >= 60 ? text.replace(/ min$/, "") : text;
}

/** Monday = 0 ... Sunday = 6, for a local date YYYY-MM-DD (never shifted by a time zone). */
export function weekdayIndex(iso: string): number {
  const date = utcDate(iso);
  return Number.isNaN(date.getTime()) ? -1 : (date.getUTCDay() + 6) % 7;
}

/** The seven weekday values of a payload, or undefined for an old or malformed payload. */
export function weekdayMaximums(payload: Pick<HomeworkPayload, "daily_max_weekdays">): number[] | undefined {
  const values = payload.daily_max_weekdays;
  return Array.isArray(values) && values.length === 7 && values.every((v) => Number.isFinite(v))
    ? values
    : undefined;
}

export interface DayMaximum {
  /** The effective maximum of the date; undefined when the payload says nothing. */
  max: number | undefined;
  /** The normal maximum of that weekday. */
  normal: number | undefined;
  /** The effective maximum differs from that weekday's normal value. */
  adjusted: boolean;
}

/**
 * The effective daily maximum of a date: the override of that date when there is one, else the
 * weekday's value (Monday = index 0), else (an old payload) `daily_max_minutes`.
 */
export function dayMaximum(
  payload: Pick<HomeworkPayload, "daily_max_weekdays" | "daily_max_minutes" | "daily_max_overrides"> | undefined,
  date: string,
): DayMaximum {
  if (!payload) return { max: undefined, normal: undefined, adjusted: false };
  const weekdays = weekdayMaximums(payload);
  const index = weekdayIndex(date);
  const fromWeekday = weekdays && index >= 0 ? weekdays[index] : undefined;
  const normal =
    fromWeekday ?? (typeof payload.daily_max_minutes === "number" ? payload.daily_max_minutes : undefined);
  const override = payload.daily_max_overrides?.[date];
  if (typeof override === "number") {
    return { max: override, normal, adjusted: override !== normal };
  }
  return { max: normal, normal, adjusted: false };
}

// -- proposals --

/** An optimistic answer to a proposal, until the backend has confirmed it. */
export type ProposalAnswer = Pick<Proposal, "status" | "closed" | "answered_by">;

/** The proposals with the optimistic answers applied. */
export function applyProposalOverlay(
  proposals: readonly Proposal[],
  overlay: ReadonlyMap<string, ProposalAnswer>,
): Proposal[] {
  return proposals.map((proposal) => {
    const answer = overlay.get(proposal.id);
    return answer ? { ...proposal, ...answer } : proposal;
  });
}

export const isOpenProposal = (proposal: Proposal): boolean => proposal.status === "proposed";

/**
 * The lowest maximum that an open period proposal gives a date (not accepted yet, so without
 * effect), or undefined when no open proposal covers it.
 */
export function proposedMaximum(proposals: readonly Proposal[], date: string): number | undefined {
  let lowest: number | undefined;
  for (const proposal of proposals) {
    if (!isOpenProposal(proposal) || proposal.kind !== "period") continue;
    if (proposal.start === undefined || proposal.end === undefined) continue;
    if (typeof proposal.minutes !== "number") continue;
    if (date < proposal.start || date > proposal.end) continue;
    if (lowest === undefined || proposal.minutes < lowest) lowest = proposal.minutes;
  }
  return lowest;
}

/** "23–27 nov", "30 nov – 4 dec" or "23 nov" */
export function formatRange(start: string, end: string, language: string): string {
  const first = utcDate(start);
  const last = utcDate(end);
  if (Number.isNaN(first.getTime()) || Number.isNaN(last.getTime())) return `${start} – ${end}`;
  const month = (date: Date): string =>
    new Intl.DateTimeFormat(language, { timeZone: "UTC", month: "short" })
      .format(date)
      .replace(/\./g, "");
  const a = `${first.getUTCDate()} ${month(first)}`;
  const b = `${last.getUTCDate()} ${month(last)}`;
  if (a === b && start === end) return a;
  if (first.getUTCMonth() === last.getUTCMonth() && first.getUTCFullYear() === last.getUTCFullYear()) {
    return `${first.getUTCDate()}–${b}`;
  }
  return `${a} – ${b}`;
}

/** The uid of the item a subtask uid belongs to. */
export function parentUid(subtaskUid: string): string {
  const index = subtaskUid.indexOf(":sub:");
  return index < 0 ? subtaskUid : subtaskUid.slice(0, index);
}

/** The current date of a not-done subtask (the backend rule); a done one does not move. */
export function currentDate(subtask: Subtask, planned: string, itemDate: string, today: string): string {
  if (subtask.completed) return subtask.date;
  const moved = planned < today ? today : planned;
  return moved > itemDate ? itemDate : moved;
}

/** The items with the optimistic subtask edits and deletions applied. */
export function applySubtaskEdits(
  items: readonly HomeworkItem[],
  edits: ReadonlyMap<string, SubtaskEdit>,
  today: string,
): HomeworkItem[] {
  if (edits.size === 0) return [...items];
  return items.map((item) => {
    const subtasks = item.subtasks;
    if (!subtasks?.some((subtask) => edits.has(subtask.uid))) return item;
    const next: Subtask[] = [];
    for (const subtask of subtasks) {
      const edit = edits.get(subtask.uid);
      if (!edit) next.push(subtask);
      else if (!edit.deleted) {
        const planned = edit.planned ?? subtask.planned;
        next.push({
          ...subtask,
          title: edit.title ?? subtask.title,
          planned,
          ...(edit.minutes !== undefined ? { minutes: edit.minutes } : {}),
          date: currentDate(subtask, planned, item.date, today),
        });
      }
    }
    return withSubtasks(item, next);
  });
}

/** The edit's fields are what the subtask now shows (the backend has caught up). */
export function reflectsEdit(subtask: Subtask | undefined, edit: SubtaskEdit): boolean {
  if (edit.deleted) return subtask === undefined;
  if (!subtask) return true;
  return (
    (edit.title === undefined || subtask.title === edit.title) &&
    (edit.planned === undefined || subtask.planned === edit.planned) &&
    (edit.minutes === undefined || (subtask.minutes ?? null) === edit.minutes)
  );
}

export type Entry =
  | { type: "item"; item: HomeworkItem }
  | { type: "subtask"; subtask: Subtask; parent: HomeworkItem };

/** The key of the group of overdue subtasks (never a date). */
export const OVERDUE_GROUP = "overdue";

export interface EntryGroup {
  date: string;
  kind: DayKind | "overdue";
  entries: Entry[];
}

/**
 * Items and subtasks per day. Subtasks sit on their current date. Overdue ones (the item
 * date has passed) are always shown, in a separate group at the top, so the "past days"
 * switch cannot hide them. Done subtasks follow `showCompleted` like items do. Within a
 * day the items come first, then the subtasks.
 */
export function groupEntries(items: readonly HomeworkItem[], options: FilterOptions): EntryGroup[] {
  const last = addDays(options.today, options.daysAhead);
  const groups = new Map<string, EntryGroup>();
  const add = (date: string, entry: Entry): void => {
    let group = groups.get(date);
    if (!group) {
      group = {
        date,
        kind: date === OVERDUE_GROUP ? "overdue" : kindOf(date, options.today),
        entries: [],
      };
      groups.set(date, group);
    }
    group.entries.push(entry);
  };
  for (const item of filterItems(items, options)) add(item.date, { type: "item", item });
  const subtasks: [string, Entry][] = [];
  for (const parent of items) {
    if (parent.disabled === true) continue;
    for (const subtask of parent.subtasks ?? []) {
      if (subtask.completed && !options.showCompleted && !options.keep?.has(subtask.uid)) continue;
      // A kept (just ticked) subtask of a passed lesson stays where it was under the finger.
      const keptOverdue =
        options.keep?.has(subtask.uid) === true && parent.date < options.today;
      if (subtask.overdue || keptOverdue) {
        subtasks.push([OVERDUE_GROUP, { type: "subtask", subtask, parent }]);
        continue;
      }
      if (subtask.date < options.today ? !options.showPast : subtask.date > last) continue;
      subtasks.push([subtask.date, { type: "subtask", subtask, parent }]);
    }
  }
  for (const [date, entry] of subtasks) add(date, entry);
  return [...groups.values()].sort((a, b) => {
    if (a.kind === "overdue" || b.kind === "overdue") {
      return a.kind === b.kind ? 0 : a.kind === "overdue" ? -1 : 1;
    }
    return a.date.localeCompare(b.date);
  });
}

/** "di 17 nov" / "Tue 17 Nov" */
export function formatShortDay(iso: string, language: string): string {
  const date = utcDate(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(language, {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
  })
    .format(date)
    .replace(/\./g, "");
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
  language: CardLanguage;
  card_id: string;
}

/** The progress periods, in display order, with the config option that shows each. */
export const PROGRESS_PERIODS = [
  { period: "next_day", option: "show_progress_tomorrow" },
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
    language: config.language === "nl" || config.language === "en" ? config.language : "auto",
    card_id: typeof config.card_id === "string" ? config.card_id : "",
  };
}

// -- manual labels --

/** Key of one manual label on one item (used for optimistic removal). */
export function labelKey(uid: string, labelId: string): string {
  return `${uid}\u0000${labelId}`;
}

/**
 * The items without the manual labels that are being removed. An item that is in the
 * planner only because of manual labels (no Magister type) leaves with its last label.
 */
export function applyLabelRemovals(
  items: readonly HomeworkItem[],
  hidden: ReadonlySet<string>,
): HomeworkItem[] {
  if (hidden.size === 0) return [...items];
  const result: HomeworkItem[] = [];
  for (const item of items) {
    const labels = item.manual_labels.filter((label) => !hidden.has(labelKey(item.uid, label.id)));
    if (labels.length === item.manual_labels.length) {
      result.push(item);
    } else if (item.info_type !== null || labels.length > 0) {
      // The last manual label of an item whose Magister label is disabled: nothing is active.
      const nothingLeft = labels.length === 0 && item.override?.mode === "disable";
      result.push({
        ...item,
        manual_labels: labels,
        ...(nothingLeft ? { disabled: true, completed: true, is_test: false } : {}),
      });
    }
  }
  return result;
}

/** Days after today that the add-label dialog always offers (the fetch window is at least this long). */
export const MIN_LABEL_DAYS = 21;

/**
 * The first and last date the add-label dialog offers. Labels go on today or later;
 * the last date is the later of today + days ahead and the last item, but at least
 * today + 21 days. The backend still checks the real window (invalid_date).
 */
export function dateBounds(
  items: readonly HomeworkItem[],
  today: string,
  daysAhead: number,
): { min: string; max: string } {
  let max = addDays(today, Math.max(daysAhead, MIN_LABEL_DAYS));
  for (const item of items) {
    if (item.date > max) max = item.date;
  }
  return { min: today, max };
}

/** "09:10" from a local ISO datetime (read from the text, so no time zone can shift it). */
export function clockTime(iso: string): string {
  const match = /T(\d{2}:\d{2})/.exec(iso);
  return match?.[1] ?? "";
}

/** "09:10-10:00" of an appointment; empty for an all-day appointment. */
export function timeRange(appointment: Appointment): string {
  if (appointment.all_day) return "";
  const start = clockTime(appointment.start);
  const end = clockTime(appointment.end);
  return start && end ? `${start}\u2013${end}` : start;
}

// -- remembering the switches per card --

export interface Switches {
  show_completed: boolean;
  show_past: boolean;
}

/** FNV-1a, 32 bit, as 8 hex digits. */
export function hashString(text: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index++) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}

/** A short random id for `card_id`. */
export function generateCardId(): string {
  try {
    const bytes = crypto.getRandomValues(new Uint8Array(6));
    return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
  } catch {
    return Math.random().toString(36).slice(2, 14).padEnd(12, "0");
  }
}

/**
 * The localStorage key of one card: the entity, the card id (the config's `card_id`, or a
 * hash of entity and title) and a hash of the config values, so saving a changed config
 * starts from the configured switches again.
 */
export function storageKey(config: NormalizedConfig): string {
  const id = config.card_id || hashString(`${config.entity}\u0000${config.title}`);
  const settings = hashString(
    JSON.stringify([
      config.entity,
      config.title,
      config.card_id,
      config.language,
      config.show_completed,
      config.show_past,
      config.days_ahead,
      config.show_progress_tomorrow,
      config.show_progress_week,
      config.show_progress_next_week,
    ]),
  );
  return `magister-homework-card:${config.entity}:${id}:${settings}`;
}

/** The remembered switches, or undefined without storage or a valid value. Never throws. */
export function loadSwitches(key: string): Switches | undefined {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return undefined;
    const value = JSON.parse(raw) as Partial<Record<keyof Switches, unknown>> | null;
    if (
      typeof value?.show_completed === "boolean" &&
      typeof value.show_past === "boolean"
    ) {
      return { show_completed: value.show_completed, show_past: value.show_past };
    }
  } catch {
    // no storage, or garbage in it
  }
  return undefined;
}

/** Remember the switches; silently does nothing without storage. */
export function saveSwitches(key: string, switches: Switches): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(switches));
  } catch {
    // no storage, or full
    return;
  }
  // Values of earlier configs of this card (same entity and id) are of no use any more.
  try {
    const prefix = key.slice(0, key.lastIndexOf(":") + 1);
    const stale: string[] = [];
    for (let index = 0; index < window.localStorage.length; index++) {
      const other = window.localStorage.key(index);
      if (other !== null && other !== key && other.startsWith(prefix)) stale.push(other);
    }
    for (const other of stale) window.localStorage.removeItem(other);
  } catch {
    // no storage
  }
}

// -- overrides of the Magister label (since 1.4.0) --

/** What a menu choice asks the backend to do. */
export type OverrideChange =
  | { mode: "replace"; label: LabelOption }
  | { mode: "disable" }
  | { mode: "clear" };

/** The fields of an item that an override changes. */
export type OverrideFields = Pick<HomeworkItem, "override" | "disabled" | "is_test">;

/** The default label option id of each Magister type (the type's own label). */
const DEFAULT_OPTION_IDS: Readonly<Record<number, string>> = {
  1: "default_homework",
  2: "default_test",
  3: "default_exam",
  4: "default_written_quiz",
  5: "default_oral_quiz",
};

/**
 * The state an item is in after `change`, as the backend would compute it: the active
 * labels are the effective Magister label plus the manual labels; no active labels
 * means disabled; a test is any active label of kind test.
 */
export function optimisticOverride(item: HomeworkItem, change: OverrideChange): OverrideFields {
  const manualTest = item.manual_labels.some((label) => label.kind === "test");
  switch (change.mode) {
    case "replace":
      return {
        override: { mode: "replace", label: change.label },
        disabled: false,
        is_test: change.label.kind === "test" || manualTest,
      };
    case "disable":
      return {
        override: { mode: "disable" },
        disabled: item.manual_labels.length === 0,
        is_test: manualTest,
      };
    case "clear":
      return {
        override: null,
        disabled: false,
        is_test: (item.info_type !== null && item.info_type >= 2) || manualTest,
      };
  }
}

/** The override fields an item as pushed (or answered) carries. */
export function overrideFieldsOf(item: HomeworkItem): OverrideFields {
  return {
    override: item.override ?? null,
    disabled: item.disabled === true,
    is_test: item.is_test,
  };
}

function sameOverride(a: ItemOverride | null | undefined, b: ItemOverride | null | undefined): boolean {
  if (!a || !b) return !a && !b;
  if (a.mode !== b.mode) return false;
  return a.mode === "replace" && b.mode === "replace" ? a.label.id === b.label.id : true;
}

/** Whether an item already shows the given override state. */
export function hasOverrideFields(item: HomeworkItem, fields: OverrideFields): boolean {
  return (
    sameOverride(item.override, fields.override) &&
    (item.disabled === true) === (fields.disabled === true) &&
    item.is_test === fields.is_test
  );
}

/** The items with the optimistic (not yet confirmed) overrides applied. */
export function applyOverrides(
  items: readonly HomeworkItem[],
  overlay: ReadonlyMap<string, OverrideFields>,
): HomeworkItem[] {
  if (overlay.size === 0) return [...items];
  return items.map((item) => {
    const change = overlay.get(item.uid);
    if (!change) return item;
    return {
      ...item,
      ...change,
      completed: item.progress >= 100 || change.disabled === true,
    };
  });
}

/** The things the Magister chip's menu offers for an item. */
export interface MenuActions {
  /** The label options an item can be replaced by. */
  replace: LabelOption[];
  disable: boolean;
  restore: boolean;
}

/**
 * Replacement options are the child's labels except the original's own default label
 * (and the current replacement). A disabled item can only be restored; a disabled label
 * cannot be disabled again.
 */
export function menuActions(item: HomeworkItem, options: readonly LabelOption[]): MenuActions {
  const own = item.info_type !== null ? DEFAULT_OPTION_IDS[item.info_type] : undefined;
  const current = item.override?.mode === "replace" ? item.override.label.id : undefined;
  return {
    replace:
      item.disabled === true
        ? []
        : options.filter((option) => option.id !== own && option.id !== current),
    disable: item.disabled !== true && item.override?.mode !== "disable",
    restore: item.override != null,
  };
}
