/** Study timer maths and helpers shared by both cards (see docs/reference/homework-websocket.md). */
import type { StudyTimer, TimerAction, TimerSettings, TimerState } from "./types";

export const PREWARN_MAX = 15;
export const EXTRA_MAX = 30;
/** The steps of the progress panel (the same as the planner). */
export const PANEL_STEPS = [0, 25, 50, 75, 100] as const;
/** A skew below this is network latency, not a wrong clock. */
const SKEW_MIN_MS = 2000;
/** A skew above this is not a clock difference we trust. */
const SKEW_MAX_MS = 12 * 3_600_000;

export const NO_SETTINGS: TimerSettings = { prewarn_minutes: null, extra_minutes: null };

/** An ISO timestamp as milliseconds; undefined when it does not parse. */
export function parseMs(iso: string | undefined): number | undefined {
  if (!iso) return undefined;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : undefined;
}

/**
 * The whole seconds left, from the end time (running) or the stored remainder (paused).
 * `skewMs` is the server clock minus this device's clock. Never negative; a finished timer has 0.
 */
export function remainingSeconds(timer: StudyTimer, nowMs: number, skewMs = 0): number {
  if (timer.state === "finished") return 0;
  if (timer.state === "paused") return Math.max(Math.floor(timer.remaining ?? 0), 0);
  const end = parseMs(timer.ends_at);
  if (end === undefined) return 0;
  return Math.max(Math.ceil((end - (nowMs + skewMs)) / 1000), 0);
}

/** The state as the card shows it: a running timer whose time has come is finished, also before the push. */
export function effectiveState(timer: StudyTimer, nowMs: number, skewMs = 0): TimerState {
  if (timer.state === "running" && remainingSeconds(timer, nowMs, skewMs) <= 0) return "finished";
  return timer.state;
}

/** `mm:ss`, or `h:mm:ss` from one hour. */
export function formatCountdown(totalSeconds: number): string {
  const seconds = Math.max(Math.floor(totalSeconds), 0);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const two = (n: number): string => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${two(m)}:${two(s)}` : `${two(m)}:${two(s)}`;
}

/** The share of the current countdown that has passed, 0 to 1 (a finished timer is 1). */
export function elapsedFraction(timer: StudyTimer, nowMs: number, skewMs = 0): number {
  const total = timer.minutes * 60;
  if (!(total > 0)) return 1;
  const left = remainingSeconds(timer, nowMs, skewMs);
  return Math.min(Math.max(1 - left / total, 0), 1);
}

/**
 * The server clock minus the device clock, from the answer to our own `start`: the timer was
 * created a moment ago, so `started_at` is the server's "now". Latency and small differences
 * are ignored; nothing is estimated from any other payload.
 */
export function estimateSkew(timer: StudyTimer | null, receivedMs: number): number | undefined {
  if (!timer || timer.state !== "running") return undefined;
  const started = parseMs(timer.started_at);
  const end = parseMs(timer.ends_at);
  if (started === undefined || end === undefined) return undefined;
  // Only a fresh start: its length is exactly the countdown.
  if (end - started !== timer.minutes * 60_000) return undefined;
  const skew = started - receivedMs;
  if (Math.abs(skew) < SKEW_MIN_MS || Math.abs(skew) > SKEW_MAX_MS) return 0;
  return skew;
}

/** Same timer, ignoring the optimistic noise: used to see whether a push confirms an answer. */
export function sameTimer(a: StudyTimer | null | undefined, b: StudyTimer | null | undefined): boolean {
  if (!a || !b) return !a && !b;
  return (
    a.subtask === b.subtask &&
    a.state === b.state &&
    a.minutes === b.minutes &&
    (a.state !== "paused" || a.remaining === b.remaining) &&
    (a.state === "paused" || a.ends_at === b.ends_at)
  );
}

/** Identity of one timer for announcements: an extension keeps it, a new start changes it. */
export function timerKey(timer: StudyTimer): string {
  return `${timer.subtask}|${timer.started_at}`;
}

/** Is the pre-warning applicable: the timer is longer than the setting (as the backend skips it otherwise). */
export function prewarnThreshold(timer: StudyTimer, settings: TimerSettings): number | undefined {
  const minutes = settings.prewarn_minutes;
  if (!minutes || minutes < 1) return undefined;
  return timer.minutes > minutes ? minutes * 60 : undefined;
}

export interface SubtaskInfo {
  uid: string;
  title: string;
  minutes: number;
  subject: string;
  due: string;
  label: string;
}

/** What the timer looks like right after the action, until the backend has answered (null: no timer). */
export function optimisticTimer(
  action: TimerAction,
  current: StudyTimer | null,
  nowMs: number,
  options: { info?: SubtaskInfo; extra?: number | null; skewMs?: number; secondsLeft?: number },
): StudyTimer | null {
  const server = nowMs + (options.skewMs ?? 0);
  const iso = (ms: number): string => new Date(ms).toISOString();
  switch (action) {
    case "start": {
      const info = options.info;
      if (!info) return current;
      return {
        subtask: info.uid,
        title: info.title,
        subject: info.subject,
        due: info.due,
        label: info.label,
        state: "running",
        ends_at: iso(server + info.minutes * 60_000),
        minutes: info.minutes,
        started_at: iso(server),
      };
    }
    case "pause": {
      if (!current || current.state !== "running") return current;
      const rest = { ...current };
      delete rest.ends_at;
      return { ...rest, state: "paused", remaining: Math.max(options.secondsLeft ?? 1, 1) };
    }
    case "resume": {
      if (!current || current.state !== "paused") return current;
      const rest = { ...current };
      delete rest.remaining;
      return { ...rest, state: "running", ends_at: iso(server + (current.remaining ?? 0) * 1000) };
    }
    case "extend": {
      const extra = options.extra;
      if (!current || !extra) return current;
      return { ...current, state: "running", minutes: extra, ends_at: iso(server + extra * 60_000) };
    }
    case "stop":
    case "done":
      return null;
  }
}

export type SettingsCheck =
  | { ok: true; settings: TimerSettings }
  | { ok: false; field: "prewarn_minutes" | "extra_minutes" };

function checkOne(value: unknown, max: number): number | null | undefined {
  if (value === null || value === "" || value === undefined) return null;
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isInteger(n) || n < 1 || n > max) return undefined;
  return n;
}

/** Off (null/empty) or a whole number of minutes: 1-15 before the end, 1-30 extra. */
export function validateSettings(input: {
  prewarn_minutes: unknown;
  extra_minutes: unknown;
}): SettingsCheck {
  const prewarn = checkOne(input.prewarn_minutes, PREWARN_MAX);
  if (prewarn === undefined) return { ok: false, field: "prewarn_minutes" };
  const extra = checkOne(input.extra_minutes, EXTRA_MAX);
  if (extra === undefined) return { ok: false, field: "extra_minutes" };
  return { ok: true, settings: { prewarn_minutes: prewarn, extra_minutes: extra } };
}

export function sameSettings(a: TimerSettings, b: TimerSettings): boolean {
  return a.prewarn_minutes === b.prewarn_minutes && a.extra_minutes === b.extra_minutes;
}

/** The settings of a payload (off when an older backend sends none). */
export function settingsOf(settings: TimerSettings | undefined): TimerSettings {
  return {
    prewarn_minutes: settings?.prewarn_minutes ?? null,
    extra_minutes: settings?.extra_minutes ?? null,
  };
}

/** The errors that mean this user may not operate the timer (the card then turns read-only). */
export const NOT_ALLOWED = new Set(["not_allowed_for_role", "unauthorized"]);
