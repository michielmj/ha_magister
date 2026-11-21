import type { HomeworkItem, HomeworkPayload, StudyTimer, Subtask, TimerSettings } from "../src/types";
import { TODAY, item } from "./fixtures";

/** Placeholder data only. Now in the timer tests is 2026-11-13T09:30:00Z. */
export const PARENT = "school.example.net:1:50";
export const SUB_A = `${PARENT}:sub:a`;
export const SUB_B = `${PARENT}:sub:b`;
export const NOW_ISO = "2026-11-13T09:30:00+00:00";
export const END_ISO = "2026-11-13T10:00:00+00:00";

export function sub(id: string, overrides: Partial<Subtask> = {}): Subtask {
  return {
    uid: `${PARENT}:sub:${id}`,
    title: `Stap ${id}`,
    planned: TODAY,
    date: TODAY,
    overdue: false,
    progress: 0,
    completed: false,
    last_partial: 0,
    minutes: 30,
    ...overrides,
  };
}

/** A Proefwerk on Tuesday 17 Nov with subtasks. */
export function parent(subtasks: Subtask[], overrides: Partial<HomeworkItem> = {}): HomeworkItem {
  return item({
    uid: PARENT,
    date: "2026-11-17",
    due: "2026-11-17T10:00:00+01:00",
    subject: "Engels",
    info_type: 2,
    label: "Proefwerk",
    is_test: true,
    derived: subtasks.length > 0,
    subtasks,
    ...overrides,
  });
}

export function timer(overrides: Partial<StudyTimer> = {}): StudyTimer {
  return {
    subtask: SUB_A,
    title: "Stap a",
    subject: "Engels",
    due: "2026-11-17",
    label: "Proefwerk",
    state: "running",
    ends_at: END_ISO,
    minutes: 30,
    started_at: NOW_ISO,
    ...overrides,
  };
}

export function pausedTimer(remaining = 600, overrides: Partial<StudyTimer> = {}): StudyTimer {
  const base = timer({ state: "paused", remaining, ...overrides });
  delete base.ends_at;
  return base;
}

export function finishedTimer(overrides: Partial<StudyTimer> = {}): StudyTimer {
  return timer({ state: "finished", ends_at: NOW_ISO, ...overrides });
}

export const NO_EXTRA: TimerSettings = { prewarn_minutes: null, extra_minutes: null };

export function timerPayload(
  items: HomeworkItem[],
  options: { timer?: StudyTimer | null; settings?: TimerSettings; available?: boolean } = {},
): HomeworkPayload {
  return {
    available: options.available ?? true,
    items,
    timer: options.timer ?? null,
    timer_settings: options.settings ?? NO_EXTRA,
  };
}
