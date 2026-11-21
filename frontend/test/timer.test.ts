import { describe, expect, it } from "vitest";
import {
  effectiveState,
  elapsedFraction,
  estimateSkew,
  formatCountdown,
  optimisticTimer,
  parseMs,
  prewarnThreshold,
  remainingSeconds,
  sameSettings,
  sameTimer,
  settingsOf,
  timerKey,
  validateSettings,
} from "../src/timer";
import { END_ISO, SUB_A, finishedTimer, pausedTimer, timer } from "./timer-fixtures";

const NOW = Date.parse("2026-11-13T09:30:00Z");

describe("countdown maths", () => {
  it("counts down from ends_at and rounds up to whole seconds", () => {
    expect(remainingSeconds(timer(), NOW)).toBe(1800);
    expect(remainingSeconds(timer(), NOW + 1)).toBe(1800);
    expect(remainingSeconds(timer(), NOW + 1000)).toBe(1799);
    expect(remainingSeconds(timer(), NOW + 1799_500)).toBe(1);
    expect(remainingSeconds(timer(), NOW + 1800_000)).toBe(0);
    expect(remainingSeconds(timer(), NOW + 9_999_000)).toBe(0);
  });

  it("uses the stored remainder of a paused timer and 0 for a finished one", () => {
    expect(remainingSeconds(pausedTimer(600), NOW)).toBe(600);
    expect(remainingSeconds(pausedTimer(600), NOW + 3_600_000)).toBe(600);
    expect(remainingSeconds(finishedTimer(), NOW)).toBe(0);
    expect(remainingSeconds(timer({ ends_at: "garbage" }), NOW)).toBe(0);
    expect(remainingSeconds(timer({ ends_at: undefined }), NOW)).toBe(0);
  });

  it("applies the clock skew (server minus device)", () => {
    // the server is 10 s ahead: the timer runs out 10 s earlier on this device
    expect(remainingSeconds(timer(), NOW, 10_000)).toBe(1790);
    expect(remainingSeconds(timer(), NOW, -10_000)).toBe(1810);
  });

  it("shows a running timer whose time has come as finished", () => {
    expect(effectiveState(timer(), NOW)).toBe("running");
    expect(effectiveState(timer(), NOW + 1800_000)).toBe("finished");
    expect(effectiveState(pausedTimer(0), NOW)).toBe("paused");
    expect(effectiveState(finishedTimer(), NOW)).toBe("finished");
  });

  it("formats mm:ss and h:mm:ss", () => {
    expect(formatCountdown(0)).toBe("00:00");
    expect(formatCountdown(5)).toBe("00:05");
    expect(formatCountdown(65)).toBe("01:05");
    expect(formatCountdown(1800)).toBe("30:00");
    expect(formatCountdown(3599)).toBe("59:59");
    expect(formatCountdown(3600)).toBe("1:00:00");
    expect(formatCountdown(5025)).toBe("1:23:45");
    expect(formatCountdown(-3)).toBe("00:00");
  });

  it("gives the elapsed share for the ring", () => {
    expect(elapsedFraction(timer(), NOW)).toBe(0);
    expect(elapsedFraction(timer(), NOW + 900_000)).toBe(0.5);
    expect(elapsedFraction(timer(), NOW + 9_000_000)).toBe(1);
    expect(elapsedFraction(finishedTimer(), NOW)).toBe(1);
    expect(elapsedFraction(pausedTimer(450), NOW)).toBe(0.75);
    expect(elapsedFraction(timer({ minutes: 0 }), NOW)).toBe(1);
  });
});

describe("clock skew", () => {
  it("is estimated from a fresh start only", () => {
    const fresh = timer({ started_at: "2026-11-13T09:30:10+00:00", ends_at: "2026-11-13T10:00:10+00:00" });
    expect(estimateSkew(fresh, NOW)).toBe(10_000);
    expect(estimateSkew({ ...fresh, started_at: "2026-11-13T09:29:50+00:00", ends_at: "2026-11-13T09:59:50+00:00" }, NOW)).toBe(-10_000);
  });

  it("ignores latency, a timer that is not fresh and absurd values", () => {
    expect(estimateSkew(timer(), NOW + 300)).toBe(0);
    expect(estimateSkew(timer({ started_at: "2026-11-13T09:00:00+00:00" }), NOW)).toBeUndefined();
    expect(estimateSkew(timer(), NOW + 48 * 3_600_000)).toBe(0);
    expect(estimateSkew(pausedTimer(), NOW)).toBeUndefined();
    expect(estimateSkew(null, NOW)).toBeUndefined();
    expect(estimateSkew(timer({ started_at: "x" }), NOW)).toBeUndefined();
  });

  it("parses timestamps", () => {
    expect(parseMs(undefined)).toBeUndefined();
    expect(parseMs("nope")).toBeUndefined();
    expect(parseMs("2026-11-13T09:30:00+00:00")).toBe(NOW);
  });
});

describe("optimistic timers", () => {
  const info = { uid: SUB_A, title: "Stap a", minutes: 30, subject: "Engels", due: "2026-11-17", label: "Proefwerk" };

  it("start runs for the minutes of the subtask", () => {
    const started = optimisticTimer("start", null, NOW, { info });
    expect(started).toMatchObject({ subtask: SUB_A, state: "running", minutes: 30, ends_at: END_ISO.replace("+00:00", ".000Z") });
    expect(optimisticTimer("start", null, NOW, {})).toBeNull();
  });

  it("pause keeps the seconds, resume runs on from them", () => {
    const paused = optimisticTimer("pause", timer(), NOW, { secondsLeft: 600 });
    expect(paused).toMatchObject({ state: "paused", remaining: 600 });
    expect(paused).not.toHaveProperty("ends_at");
    const resumed = optimisticTimer("resume", paused, NOW, {});
    expect(resumed).toMatchObject({ state: "running", ends_at: "2026-11-13T09:40:00.000Z" });
    expect(resumed).not.toHaveProperty("remaining");
    expect(optimisticTimer("pause", pausedTimer(), NOW, {})).toEqual(pausedTimer());
    expect(optimisticTimer("resume", timer(), NOW, {})).toEqual(timer());
  });

  it("extend restarts the countdown with the extra minutes, stop and done remove the timer", () => {
    expect(optimisticTimer("extend", finishedTimer(), NOW, { extra: 5 })).toMatchObject({
      state: "running",
      minutes: 5,
      ends_at: "2026-11-13T09:35:00.000Z",
    });
    expect(optimisticTimer("extend", finishedTimer(), NOW, { extra: null })).toEqual(finishedTimer());
    expect(optimisticTimer("stop", timer(), NOW, {})).toBeNull();
    expect(optimisticTimer("done", timer(), NOW, {})).toBeNull();
  });

  it("compares timers and settings", () => {
    expect(sameTimer(timer(), timer())).toBe(true);
    expect(sameTimer(timer(), timer({ ends_at: "2026-11-13T10:01:00+00:00" }))).toBe(false);
    expect(sameTimer(pausedTimer(5), pausedTimer(5))).toBe(true);
    expect(sameTimer(pausedTimer(5), pausedTimer(6))).toBe(false);
    expect(sameTimer(null, undefined)).toBe(true);
    expect(sameTimer(timer(), null)).toBe(false);
    expect(timerKey(timer())).toBe(`${SUB_A}|2026-11-13T09:30:00+00:00`);
    expect(sameSettings({ prewarn_minutes: 2, extra_minutes: null }, { prewarn_minutes: 2, extra_minutes: null })).toBe(true);
    expect(settingsOf(undefined)).toEqual({ prewarn_minutes: null, extra_minutes: null });
  });
});

describe("settings validation", () => {
  it("accepts off and whole minutes within range", () => {
    expect(validateSettings({ prewarn_minutes: "", extra_minutes: "" })).toEqual({
      ok: true,
      settings: { prewarn_minutes: null, extra_minutes: null },
    });
    expect(validateSettings({ prewarn_minutes: "15", extra_minutes: 30 })).toEqual({
      ok: true,
      settings: { prewarn_minutes: 15, extra_minutes: 30 },
    });
    expect(validateSettings({ prewarn_minutes: null, extra_minutes: "1" })).toEqual({
      ok: true,
      settings: { prewarn_minutes: null, extra_minutes: 1 },
    });
  });

  it("rejects values outside 1-15 and 1-30 and non-integers, naming the field", () => {
    expect(validateSettings({ prewarn_minutes: "16", extra_minutes: "" })).toEqual({ ok: false, field: "prewarn_minutes" });
    expect(validateSettings({ prewarn_minutes: "0", extra_minutes: "" })).toEqual({ ok: false, field: "prewarn_minutes" });
    expect(validateSettings({ prewarn_minutes: "2.5", extra_minutes: "" })).toEqual({ ok: false, field: "prewarn_minutes" });
    expect(validateSettings({ prewarn_minutes: "abc", extra_minutes: "" })).toEqual({ ok: false, field: "prewarn_minutes" });
    expect(validateSettings({ prewarn_minutes: 5, extra_minutes: 31 })).toEqual({ ok: false, field: "extra_minutes" });
    expect(validateSettings({ prewarn_minutes: 5, extra_minutes: -1 })).toEqual({ ok: false, field: "extra_minutes" });
  });

  it("the pre-warning only applies to a timer that is longer than the setting", () => {
    expect(prewarnThreshold(timer({ minutes: 30 }), { prewarn_minutes: 5, extra_minutes: null })).toBe(300);
    expect(prewarnThreshold(timer({ minutes: 5 }), { prewarn_minutes: 5, extra_minutes: null })).toBeUndefined();
    expect(prewarnThreshold(timer(), { prewarn_minutes: null, extra_minutes: null })).toBeUndefined();
  });
});
