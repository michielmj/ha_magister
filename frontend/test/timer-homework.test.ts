import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import { TRANSLATIONS } from "../src/translations";
import type { HomeworkPayload, StudyTimer, TimerSettings } from "../src/types";
import { TIMER, TIMER_SETTINGS } from "../src/timer-controller";
import { ENTITY, flush, mount, root, wsError } from "./helpers";
import {
  NO_EXTRA,
  PARENT,
  SUB_A,
  SUB_B,
  finishedTimer,
  parent,
  pausedTimer,
  sub,
  timer,
  timerPayload,
} from "./timer-fixtures";

beforeEach(() => {
  vi.useFakeTimers({
    toFake: ["Date", "setTimeout", "clearTimeout", "setInterval", "clearInterval"],
  });
  vi.setSystemTime(new Date("2026-11-13T09:30:00Z"));
  window.localStorage.clear();
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const q = (card: MagisterHomeworkCard, selector: string): HTMLElement => {
  const found = root(card).querySelector<HTMLElement>(selector);
  if (!found) throw new Error(`no ${selector}`);
  return found;
};
const qb = q as (card: MagisterHomeworkCard, selector: string) => HTMLButtonElement;
const qs = q as (card: MagisterHomeworkCard, selector: string) => HTMLSelectElement;
const has = (card: MagisterHomeworkCard, selector: string): boolean =>
  root(card).querySelector(selector) !== null;
const text = (card: MagisterHomeworkCard, selector: string): string => q(card, selector).textContent.replace(/\s+/g, " ").trim();
const act = (act: string, where: string, uid = SUB_A): string =>
  `[data-timer-act="${act}"][data-timer-uid="${uid}"][data-timer-where="${where}"]`;
const rowOf = (uid = SUB_A): string => `li[data-uid="${uid}"]`;
const live = (card: MagisterHomeworkCard): string => text(card, ".timer-live");

interface Setup {
  timer?: StudyTimer | null;
  settings?: TimerSettings;
  language?: string;
  callWS?: ReturnType<typeof vi.fn>;
  config?: Record<string, unknown>;
  subtasks?: ReturnType<typeof sub>[];
}

async function setup(options: Setup = {}) {
  const callWS = options.callWS ?? vi.fn();
  const { card, connection } = await mount(
    { days_ahead: 14, ...options.config },
    callWS,
    options.language ?? "en",
  );
  const subtasks = options.subtasks ?? [sub("a"), sub("b", { minutes: 15 })];
  const push = async (next: HomeworkPayload): Promise<void> => {
    connection.push(next);
    await flush(card);
  };
  await push(
    timerPayload([parent(subtasks)], {
      timer: options.timer ?? null,
      settings: options.settings ?? NO_EXTRA,
    }),
  );
  const items = [parent(subtasks)];
  return { card, connection, callWS, push, items };
}

async function click(card: MagisterHomeworkCard, selector: string): Promise<void> {
  qb(card, selector).click();
  await flush(card);
}

const T = TRANSLATIONS.en.timer;

describe("timer controls on subtask rows", () => {
  it("shows no timer controls when the backend predates the timer", async () => {
    const { card, connection } = await mount({ days_ahead: 14 });
    connection.push({ available: true, items: [parent([sub("a")])] });
    await flush(card);
    expect(has(card, ".timer-start")).toBe(false);
    expect(has(card, "[data-timer-settings-button]")).toBe(false);
    expect(has(card, ".timer-live")).toBe(false);
  });

  it("offers a start button only on subtasks with minutes that are not done", async () => {
    const { card } = await setup({
      subtasks: [
        sub("a"),
        sub("b", { minutes: null }),
        sub("c", { minutes: undefined }),
        sub("d", { progress: 100, completed: true }),
      ],
    });
    expect(has(card, `[data-timer-start="${PARENT}:sub:a"]`)).toBe(true);
    expect(has(card, `[data-timer-start="${PARENT}:sub:b"]`)).toBe(false);
    expect(has(card, `[data-timer-start="${PARENT}:sub:c"]`)).toBe(false);
    expect(has(card, `[data-timer-start="${PARENT}:sub:d"]`)).toBe(false);
    expect(qb(card, ".timer-start").getAttribute("aria-label")).toBe("Start timer for Stap a (30 min)");
  });

  it("starts a timer optimistically and sends start", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: timer() });
    const { card } = await setup({ callWS });
    await click(card, ".timer-start");
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "start", subtask: SUB_A });
    expect(text(card, `${rowOf()} .countdown`)).toContain("30:00");
    expect(has(card, `[data-timer-start="${SUB_A}"]`)).toBe(false);
    expect(has(card, act("pause", "row"))).toBe(true);
    expect(has(card, act("stop", "row"))).toBe(true);
    // focus moves to the pause button that replaced the start button
    expect(root(card).activeElement).toBe(q(card, act("pause", "row")));
  });

  it("shows the timer bar with the title and the countdown, also for a subtask on another day", async () => {
    const { card } = await setup({
      timer: timer({ subtask: `${PARENT}:sub:z`, title: "Verre stap" }),
      subtasks: [sub("a"), sub("z", { planned: "2026-12-30", date: "2026-12-30" })],
      config: { days_ahead: 1 },
    });
    expect(has(card, `li[data-uid="${PARENT}:sub:z"]`)).toBe(false);
    expect(text(card, ".timer-bar .timer-bar-title")).toBe("Verre stap");
    expect(text(card, ".timer-bar .countdown")).toContain("30:00");
    expect(text(card, ".timer-bar .meta")).toBe("Engels · Test · Tue 17 Nov");
    // the bar has the controls too, so the timer can be stopped without finding the row
    expect(has(card, act("pause", "bar", `${PARENT}:sub:z`))).toBe(true);
  });

  it("has no bar without a timer", async () => {
    const { card } = await setup();
    expect(has(card, ".timer-bar")).toBe(false);
  });

  it("counts down every second and shows h:mm:ss for long timers", async () => {
    const { card } = await setup({ timer: timer({ ends_at: "2026-11-13T11:00:00+00:00", minutes: 90 }) });
    expect(text(card, ".timer-bar .countdown")).toContain("1:30:00");
    await vi.advanceTimersByTimeAsync(3000);
    await flush(card);
    expect(text(card, ".timer-bar .countdown")).toContain("1:29:57");
  });

  it("ticks only while a timer runs", async () => {
    const { card, push } = await setup();
    const base = vi.getTimerCount();
    await push(timerPayload([parent([sub("a")])], { timer: timer() }));
    expect(vi.getTimerCount()).toBe(base + 1);
    await push(timerPayload([parent([sub("a")])], { timer: pausedTimer() }));
    expect(vi.getTimerCount()).toBe(base);
    await push(timerPayload([parent([sub("a")])], { timer: timer() }));
    expect(vi.getTimerCount()).toBe(base + 1);
    await push(timerPayload([parent([sub("a")])], { timer: finishedTimer() }));
    // (the end announcement clears itself after a while)
    await vi.advanceTimersByTimeAsync(11_000);
    expect(vi.getTimerCount()).toBe(base);
    await push(timerPayload([parent([sub("a")])], { timer: timer() }));
    card.remove();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("turns a running timer into the finished state when the time has come, and stops ticking", async () => {
    const { card } = await setup({ timer: timer({ ends_at: "2026-11-13T09:30:03+00:00", minutes: 1 }) });
    const base = vi.getTimerCount();
    await vi.advanceTimersByTimeAsync(3000);
    await flush(card);
    expect(text(card, `${rowOf()} .timer-state`)).toBe("Time is up");
    expect(has(card, act("done", "row"))).toBe(true);
    await vi.advanceTimersByTimeAsync(11_000);
    expect(vi.getTimerCount()).toBe(base - 1);
  });

  it("corrects for a device clock that is behind the server", async () => {
    // the server says the timer started 10 s after this device's clock
    const answer = timer({ started_at: "2026-11-13T09:30:10+00:00", ends_at: "2026-11-13T10:00:10+00:00" });
    const callWS = vi.fn().mockResolvedValue({ timer: answer });
    const { card } = await setup({ callWS });
    await click(card, ".timer-start");
    expect(text(card, `${rowOf()} .countdown`)).toContain("30:00");
    await vi.advanceTimersByTimeAsync(1000);
    await flush(card);
    expect(text(card, `${rowOf()} .countdown`)).toContain("29:59");
  });
});

describe("pause, resume and the other buttons", () => {
  it("pauses optimistically and resumes", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: pausedTimer(1790) });
    const { card } = await setup({ timer: timer(), callWS });
    await vi.advanceTimersByTimeAsync(10_000);
    await click(card, act("pause", "row"));
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "pause" });
    expect(text(card, `${rowOf()} .timer-state`)).toBe("Paused");
    expect(text(card, `${rowOf()} .countdown`)).toContain("29:50");
    expect(root(card).activeElement).toBe(q(card, act("resume", "row")));
    // paused: no further ticking
    await vi.advanceTimersByTimeAsync(5000);
    await flush(card);
    expect(text(card, `${rowOf()} .countdown`)).toContain("29:50");
    callWS.mockResolvedValue({ timer: timer() });
    await click(card, act("resume", "row"));
    expect(callWS).toHaveBeenLastCalledWith({ type: TIMER, entity_id: ENTITY, action: "resume" });
    expect(has(card, act("pause", "row"))).toBe(true);
  });

  it("keeps the confirmed state until the push arrives, then the push wins", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: pausedTimer(1795) });
    const { card, push } = await setup({ timer: timer(), callWS });
    await click(card, act("pause", "bar"));
    expect(text(card, ".timer-bar .timer-state")).toBe("Paused");
    await push(timerPayload([parent([sub("a")])], { timer: pausedTimer(1795) }));
    expect(text(card, ".timer-bar .timer-state")).toBe("Paused");
  });

  it("a push from elsewhere (another device) replaces the shown timer", async () => {
    const { card, push } = await setup({ timer: timer() });
    await push(timerPayload([parent([sub("a")])], { timer: null }));
    expect(has(card, ".timer-bar")).toBe(false);
    expect(has(card, `[data-timer-start="${SUB_A}"]`)).toBe(true);
  });
});

describe("starting while another timer runs", () => {
  const items = [sub("a"), sub("b", { minutes: 15 })];

  it("asks for confirmation and sends nothing until it is given", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: timer({ subtask: SUB_B, title: "Stap b", minutes: 15 }) });
    const { card } = await setup({ timer: timer(), callWS, subtasks: items });
    await click(card, `[data-timer-start="${SUB_B}"]`);
    expect(callWS).not.toHaveBeenCalled();
    expect(text(card, `${rowOf(SUB_B)} .timer-confirm span`)).toBe(
      "A timer is already running for Stap a. Stop it and start this one?",
    );
    // the focus is on the safe choice
    expect(root(card).activeElement).toBe(q(card, ".timer-confirm [data-timer-cancel]"));
    await click(card, `${rowOf(SUB_B)} [data-timer-replace]`);
    expect(callWS).toHaveBeenCalledWith({
      type: TIMER,
      entity_id: ENTITY,
      action: "start",
      subtask: SUB_B,
      replace: true,
    });
    expect(has(card, ".timer-confirm")).toBe(false);
    expect(text(card, ".timer-bar .timer-bar-title")).toBe("Stap b");
  });

  it("cancel closes the question, keeps the timer and returns the focus", async () => {
    const callWS = vi.fn();
    const { card } = await setup({ timer: timer(), callWS, subtasks: items });
    await click(card, `[data-timer-start="${SUB_B}"]`);
    await click(card, ".timer-confirm [data-timer-cancel]");
    expect(has(card, ".timer-confirm")).toBe(false);
    expect(callWS).not.toHaveBeenCalled();
    expect(root(card).activeElement).toBe(q(card, `[data-timer-start="${SUB_B}"]`));
    expect(text(card, ".timer-bar .timer-bar-title")).toBe("Stap a");
  });

  it("Escape cancels the question", async () => {
    const { card } = await setup({ timer: timer(), subtasks: items });
    await click(card, `[data-timer-start="${SUB_B}"]`);
    q(card, ".timer-confirm").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await flush(card);
    expect(has(card, ".timer-confirm")).toBe(false);
  });

  it("also asks when the running timer is paused", async () => {
    const { card } = await setup({ timer: pausedTimer(), subtasks: items });
    await click(card, `[data-timer-start="${SUB_B}"]`);
    expect(has(card, ".timer-confirm")).toBe(true);
  });

  it("does not ask when the timer has run out: it is replaced without replace", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: timer({ subtask: SUB_B, title: "Stap b", minutes: 15 }) });
    const { card } = await setup({ timer: finishedTimer(), callWS, subtasks: items });
    await click(card, `[data-timer-start="${SUB_B}"]`);
    expect(has(card, ".timer-confirm")).toBe(false);
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "start", subtask: SUB_B });
  });

  it("says so when the backend knows a timer that this card did not show yet, and rolls back", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("timer_running"));
    const { card } = await setup({ callWS, subtasks: items });
    await click(card, `[data-timer-start="${SUB_A}"]`);
    expect(text(card, ".toast span")).toBe(T.errors.timer_running);
    expect(has(card, `${rowOf()} .countdown`)).toBe(false);
    expect(has(card, `[data-timer-start="${SUB_A}"]`)).toBe(true);
  });
});

describe("when the timer has run out", () => {
  it("shows Klaar and Nog niet, and +x min only when extra minutes are set", async () => {
    const { card, push } = await setup({ timer: finishedTimer() });
    expect(text(card, `${rowOf()} .timer-state`)).toBe("Time is up");
    expect(text(card, act("done", "row"))).toContain("Done");
    expect(text(card, act("not_yet", "row"))).toBe("Not yet");
    expect(has(card, act("extend", "row"))).toBe(false);
    expect(has(card, act("extend", "bar"))).toBe(false);
    await push(
      timerPayload([parent([sub("a")])], {
        timer: finishedTimer(),
        settings: { prewarn_minutes: null, extra_minutes: 5 },
      }),
    );
    expect(text(card, act("extend", "row"))).toBe("+5 min");
    expect(qb(card, act("extend", "row")).getAttribute("aria-label")).toBe("5 extra minutes for Stap a");
  });

  it("offers no +x min while the timer runs or is paused, whatever the setting", async () => {
    const settings = { prewarn_minutes: null, extra_minutes: 5 };
    const { card, push } = await setup({ timer: timer(), settings });
    expect(has(card, '[data-timer-act="extend"]')).toBe(false);
    await push(timerPayload([parent([sub("a")])], { timer: pausedTimer(), settings }));
    expect(has(card, '[data-timer-act="extend"]')).toBe(false);
    expect(has(card, '[data-timer-act="done"]')).toBe(false);
  });

  it("+x min sends extend and runs again", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: timer({ minutes: 5, ends_at: "2026-11-13T09:35:00+00:00" }) });
    const { card } = await setup({
      timer: finishedTimer(),
      settings: { prewarn_minutes: null, extra_minutes: 5 },
      callWS,
    });
    await click(card, act("extend", "row"));
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "extend" });
    expect(text(card, `${rowOf()} .countdown`)).toContain("05:00");
    expect(has(card, act("extend", "row"))).toBe(false);
  });

  it("Klaar sends done, ticks the subtask and removes the timer", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: null });
    const { card } = await setup({ timer: finishedTimer(), callWS });
    await click(card, act("done", "row"));
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "done" });
    expect(has(card, ".timer-bar")).toBe(false);
    expect((qb(card, `${rowOf()} input[type="checkbox"]`) as unknown as HTMLInputElement).checked).toBe(true);
  });

  it("Nog niet opens the progress panel and does not stop the timer", async () => {
    const callWS = vi.fn();
    const { card } = await setup({ timer: finishedTimer(), callWS });
    await click(card, act("not_yet", "row"));
    expect(callWS).not.toHaveBeenCalled();
    expect(has(card, ".timer-panel")).toBe(true);
    expect(text(card, ".timer-panel-title")).toBe("How far are you?");
  });
});

describe("the progress panel", () => {
  it("preselects the current progress and opens from Stop", async () => {
    const { card } = await setup({ timer: timer(), subtasks: [sub("a", { progress: 50, last_partial: 50 })] });
    expect(has(card, ".timer-panel")).toBe(false);
    await click(card, act("stop", "row"));
    const radios = [...root(card).querySelectorAll<HTMLElement>('.timer-panel [role="radio"]')];
    expect(radios.map((radio) => radio.textContent.trim())).toEqual(["0", "25", "50", "75", "100"]);
    expect(radios.map((radio) => radio.getAttribute("aria-checked"))).toEqual(["false", "false", "true", "false", "false"]);
    expect(root(card).activeElement).toBe(radios[2]);
  });

  it("snaps a progress between the steps to the nearest one", async () => {
    const { card } = await setup({ timer: timer(), subtasks: [sub("a", { progress: 40, last_partial: 40 })] });
    await click(card, act("stop", "bar"));
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("50");
  });

  it("Save and stop sends stop with the chosen progress, in one command", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: null });
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("stop", "row"));
    await click(card, '.timer-panel [role="radio"]:nth-child(4)');
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("75");
    await click(card, ".timer-panel .primary");
    expect(callWS).toHaveBeenCalledTimes(1);
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "stop", progress: 75 });
    expect(has(card, ".timer-panel")).toBe(false);
    expect(has(card, ".timer-bar")).toBe(false);
    // the subtask shows the progress at once
    expect(text(card, `${rowOf()} .percent`)).toBe("75%");
    // the focus goes to the start button of the subtask, not to nowhere
    expect(root(card).activeElement).toBe(q(card, `[data-timer-start="${SUB_A}"]`));
  });

  it("Stop without progress sends stop without it", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: null });
    const { card } = await setup({ timer: timer(), callWS, subtasks: [sub("a", { progress: 25, last_partial: 25 })] });
    await click(card, act("stop", "row"));
    await click(card, ".timer-panel .discard");
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "stop" });
    expect(text(card, `${rowOf()} .percent`)).toBe("25%");
  });

  it("Nog niet then Save and stop sends the progress too", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: null });
    const { card } = await setup({ timer: finishedTimer(), callWS });
    await click(card, act("not_yet", "bar"));
    await click(card, ".timer-panel .primary");
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "stop", progress: 0 });
  });

  it("is keyboard operable: arrows move the choice, Escape closes and returns the focus", async () => {
    const { card } = await setup({ timer: timer() });
    await click(card, act("stop", "row"));
    const key = async (name: string): Promise<void> => {
      (root(card).activeElement as HTMLElement).dispatchEvent(
        new KeyboardEvent("keydown", { key: name, bubbles: true, composed: true, cancelable: true }),
      );
      await flush(card);
    };
    await key("ArrowRight");
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("25");
    expect(root(card).activeElement?.textContent.trim()).toBe("25");
    await key("End");
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("100");
    await key("ArrowRight");
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("100");
    await key("Home");
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("0");
    await key("ArrowLeft");
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("0");
    await key("ArrowDown");
    await key("ArrowUp");
    await key("x");
    await key("Escape");
    expect(has(card, ".timer-panel")).toBe(false);
    // back on the button that opened it (the bar's, which comes first)
    expect(root(card).activeElement).toBe(q(card, act("stop", "bar")));
  });

  it("Cancel closes it without sending anything", async () => {
    const callWS = vi.fn();
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("stop", "row"));
    await click(card, ".timer-panel .cancel");
    expect(has(card, ".timer-panel")).toBe(false);
    expect(callWS).not.toHaveBeenCalled();
  });

  it("closes when the timer is stopped elsewhere", async () => {
    const { card, push } = await setup({ timer: timer() });
    await click(card, act("stop", "row"));
    await push(timerPayload([parent([sub("a")])], { timer: null }));
    expect(has(card, ".timer-panel")).toBe(false);
  });

  it("its buttons are disabled while the connection is down", async () => {
    const { card, connection } = await setup({ timer: timer() });
    await click(card, act("stop", "row"));
    connection.emit("disconnected");
    await flush(card);
    expect(qb(card, ".timer-panel .primary").disabled).toBe(true);
    expect(qb(card, ".timer-panel .discard").disabled).toBe(true);
    expect(qb(card, act("pause", "row")).disabled).toBe(true);
    expect(has(card, `[data-timer-start="${SUB_B}"]`)).toBe(false);
  });
});

describe("errors and rollback", () => {
  it("rolls a failed stop back: the timer and the progress return, with a translated message", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("no_timer"));
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("stop", "row"));
    await click(card, '.timer-panel [role="radio"]:nth-child(3)');
    await click(card, ".timer-panel .primary");
    expect(has(card, ".timer-bar")).toBe(true);
    expect(text(card, `${rowOf()} .percent`)).toBe("0%");
    expect(text(card, ".toast span")).toBe(T.errors.no_timer);
  });

  it("rolls a failed start back", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("subtask_completed"));
    const { card } = await setup({ callWS });
    await click(card, ".timer-start");
    expect(has(card, ".timer-bar")).toBe(false);
    expect(has(card, `[data-timer-start="${SUB_A}"]`)).toBe(true);
    expect(text(card, ".toast span")).toBe(T.errors.subtask_completed);
  });

  it("has a translated message for every error code of the timer commands", async () => {
    const codes = Object.keys(T.errors);
    expect(codes.sort()).toEqual(
      [
        "default",
        "timer_running",
        "extra_not_set",
        "invalid_format",
        "no_minutes",
        "no_timer",
        "not_allowed_for_role",
        "not_found",
        "subtask_completed",
        "subtask_not_found",
        "timer_not_finished",
        "timer_wrong_state",
        "unauthorized",
      ].sort(),
    );
    for (const language of ["en", "nl"] as const) {
      for (const code of codes) {
        const callWS = vi.fn().mockRejectedValue(wsError(code));
        const { card } = await setup({ callWS, language });
        await click(card, ".timer-start");
        const errors = TRANSLATIONS[language].timer.errors;
        expect(text(card, ".toast span")).toBe(errors[code]);
        expect(errors[code]).not.toBe("");
        document.body.innerHTML = "";
      }
    }
  });

  it("uses the default message for an unknown code", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("something_new"));
    const { card } = await setup({ callWS });
    await click(card, ".timer-start");
    expect(text(card, ".toast span")).toBe(T.errors.default);
  });

  it("shows not_allowed_for_role translated, and keeps the controls for other users", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("not_allowed_for_role"));
    const { card } = await setup({ callWS, language: "nl" });
    await click(card, ".timer-start");
    expect(text(card, ".toast span")).toBe(TRANSLATIONS.nl.timer.errors.not_allowed_for_role);
    expect(qb(card, ".timer-start").disabled).toBe(false);
  });

  it("an older failed request does not undo a newer one", async () => {
    let rejectFirst: (error: unknown) => void = () => undefined;
    const callWS = vi
      .fn()
      .mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectFirst = reject; }))
      .mockResolvedValueOnce({ timer: pausedTimer(1800) });
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("pause", "row"));
    await click(card, act("resume", "row"));
    rejectFirst(wsError("timer_wrong_state"));
    await flush(card);
    expect(has(card, ".toast")).toBe(false);
  });

  it("a stale refusal still settles the optimistic progress, so a push shows its value", async () => {
    const rejects: ((error: unknown) => void)[] = [];
    const callWS = vi.fn().mockImplementation(
      () => new Promise((_resolve, reject) => { rejects.push(reject); }),
    );
    const { card, push } = await setup({ timer: finishedTimer(), callWS });
    await click(card, act("done", "row"));
    expect((qb(card, `${rowOf()} input[type="checkbox"]`) as unknown as HTMLInputElement).checked).toBe(true);
    await click(card, `[data-timer-start="${SUB_B}"]`);
    expect(rejects).toHaveLength(2);
    rejects[0]?.(wsError("timer_wrong_state"));
    rejects[1]?.(wsError("timer_wrong_state"));
    await flush(card);
    await push(
      timerPayload([parent([sub("a", { progress: 50, last_partial: 50 }), sub("b", { minutes: 15 })])], {
        timer: null,
        settings: NO_EXTRA,
      }),
    );
    expect(text(card, `${rowOf()} .percent`)).toBe("50%");
    expect((qb(card, `${rowOf()} input[type="checkbox"]`) as unknown as HTMLInputElement).checked).toBe(false);
  });

  it("shows the effective, translated label of the item in the timer bar, with a fallback", async () => {
    const { card } = await setup({ timer: timer({ label: "Huiswerk" }) });
    expect(text(card, ".timer-bar .meta")).toContain("Test");
  });
});

describe("timer settings", () => {
  const open = async (card: MagisterHomeworkCard): Promise<void> => {
    await click(card, "[data-timer-settings-button]");
  };
  const choose = async (card: MagisterHomeworkCard, id: string, value: string): Promise<void> => {
    const select = qs(card, id);
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await flush(card);
  };
  const save = async (card: MagisterHomeworkCard): Promise<void> => {
    q(card, ".timer-settings").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
  };

  it("is reachable for everyone and starts with the current values", async () => {
    const { card } = await setup({ settings: { prewarn_minutes: 2, extra_minutes: null } });
    expect(qb(card, "[data-timer-settings-button]").getAttribute("aria-label")).toBe("Timer settings");
    await open(card);
    expect(qs(card, "#timer-prewarn").value).toBe("2");
    expect(qs(card, "#timer-extra").value).toBe("");
    expect(root(card).activeElement).toBe(qs(card, "#timer-prewarn"));
    expect(qb(card, "[data-timer-settings-button]").getAttribute("aria-expanded")).toBe("true");
  });

  it("offers off and 1-15 / 1-30 minutes", async () => {
    const { card } = await setup();
    await open(card);
    const values = (id: string): string[] => [...qs(card, id).options].map((option) => option.value);
    expect(values("#timer-prewarn")).toEqual(["", ...Array.from({ length: 15 }, (_, i) => String(i + 1))]);
    expect(values("#timer-extra")).toEqual(["", ...Array.from({ length: 30 }, (_, i) => String(i + 1))]);
    expect([...qs(card, "#timer-prewarn").options][0]?.textContent).toBe("Off");
  });

  it("saves through timer_settings and applies the values at once", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer_settings: { prewarn_minutes: 2, extra_minutes: 5 } });
    const { card } = await setup({ timer: finishedTimer(), callWS });
    expect(has(card, act("extend", "row"))).toBe(false);
    await open(card);
    await choose(card, "#timer-prewarn", "2");
    await choose(card, "#timer-extra", "5");
    await save(card);
    expect(callWS).toHaveBeenCalledWith({
      type: TIMER_SETTINGS,
      entity_id: ENTITY,
      prewarn_minutes: 2,
      extra_minutes: 5,
    });
    expect(has(card, ".timer-settings")).toBe(false);
    expect(text(card, act("extend", "row"))).toBe("+5 min");
    expect(root(card).activeElement).toBe(q(card, "[data-timer-settings-button]"));
  });

  it("sends null for off", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer_settings: NO_EXTRA });
    const { card } = await setup({ settings: { prewarn_minutes: 3, extra_minutes: 4 }, callWS });
    await open(card);
    await choose(card, "#timer-prewarn", "");
    await choose(card, "#timer-extra", "");
    await save(card);
    expect(callWS).toHaveBeenCalledWith({
      type: TIMER_SETTINGS,
      entity_id: ENTITY,
      prewarn_minutes: null,
      extra_minutes: null,
    });
  });

  it("does not send when nothing changed, and closes", async () => {
    const callWS = vi.fn();
    const { card } = await setup({ settings: { prewarn_minutes: 3, extra_minutes: null }, callWS });
    await open(card);
    await save(card);
    expect(callWS).not.toHaveBeenCalled();
    expect(has(card, ".timer-settings")).toBe(false);
  });

  it("refuses values outside the range without sending", async () => {
    const callWS = vi.fn();
    const { card } = await setup({ callWS });
    await open(card);
    // a tampered form value: a select cannot offer it, a script can
    const select = qs(card, "#timer-prewarn");
    const option = document.createElement("option");
    option.value = "99";
    select.append(option);
    await choose(card, "#timer-prewarn", "99");
    await save(card);
    expect(callWS).not.toHaveBeenCalled();
    expect(text(card, ".timer-settings .timer-error")).toBe(T.errors.invalid_format);
    expect(has(card, ".timer-settings")).toBe(true);
    expect(qs(card, "#timer-prewarn").getAttribute("aria-invalid")).toBe("true");
  });

  it("rolls back and shows the translated not_allowed_for_role message in the panel", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("not_allowed_for_role"));
    const { card } = await setup({ timer: finishedTimer(), callWS, language: "nl" });
    await open(card);
    await choose(card, "#timer-extra", "5");
    await save(card);
    expect(text(card, ".timer-settings .timer-error")).toBe(TRANSLATIONS.nl.timer.errors.not_allowed_for_role);
    // the setting is not applied, and the user's input is not lost
    expect(has(card, act("extend", "row"))).toBe(false);
    expect(qs(card, "#timer-extra").value).toBe("5");
  });

  it("closes with Cancel or Escape and returns the focus to the gear", async () => {
    const { card } = await setup();
    await open(card);
    await click(card, ".timer-settings .cancel");
    expect(has(card, ".timer-settings")).toBe(false);
    expect(root(card).activeElement).toBe(q(card, "[data-timer-settings-button]"));
    await open(card);
    q(card, ".timer-settings").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await flush(card);
    expect(has(card, ".timer-settings")).toBe(false);
  });

  it("the gear toggles the panel", async () => {
    const { card } = await setup();
    await open(card);
    await open(card);
    expect(has(card, ".timer-settings")).toBe(false);
  });

  it("the other panel closes when one opens", async () => {
    const { card } = await setup({ timer: timer() });
    await click(card, act("stop", "row"));
    await open(card);
    expect(has(card, ".timer-panel")).toBe(false);
    expect(has(card, ".timer-settings")).toBe(true);
  });
});

describe("announcements for screen readers", () => {
  const settings = { prewarn_minutes: 5, extra_minutes: null };

  it("has a polite live region that is empty at first", async () => {
    const { card } = await setup({ timer: timer(), settings });
    const region = q(card, ".timer-live");
    expect(region.getAttribute("aria-live")).toBe("polite");
    expect(region.getAttribute("role")).toBe("status");
    expect(region.textContent.trim()).toBe("");
  });

  it("announces the pre-warning once, not every second", async () => {
    const { card } = await setup({ timer: timer(), settings });
    await vi.advanceTimersByTimeAsync(1_499_000);
    await flush(card);
    expect(live(card)).toBe("");
    await vi.advanceTimersByTimeAsync(1000);
    await flush(card);
    expect(live(card)).toBe("5 minutes left: Stap a");
    // the region is not rewritten on later seconds
    const node = q(card, ".timer-live").firstChild;
    await vi.advanceTimersByTimeAsync(3000);
    await flush(card);
    expect(q(card, ".timer-live").firstChild).toBe(node);
    // and it is cleared after a while
    await vi.advanceTimersByTimeAsync(11_000);
    await flush(card);
    expect(live(card)).toBe("");
  });

  it("announces the end", async () => {
    const { card } = await setup({ timer: timer({ ends_at: "2026-11-13T09:30:05+00:00", minutes: 1 }) });
    await vi.advanceTimersByTimeAsync(4000);
    await flush(card);
    expect(live(card)).toBe("");
    await vi.advanceTimersByTimeAsync(1000);
    await flush(card);
    expect(live(card)).toBe("Time is up: Stap a");
  });

  it("announces the end when the push says the timer finished", async () => {
    const { card, push } = await setup({ timer: timer(), settings });
    await push(timerPayload([parent([sub("a")])], { timer: finishedTimer(), settings }));
    expect(live(card)).toBe("Time is up: Stap a");
  });

  it("does not announce a timer that was already past the moment when the card opened", async () => {
    const { card } = await setup({ timer: timer({ ends_at: "2026-11-13T09:33:00+00:00" }), settings });
    await vi.advanceTimersByTimeAsync(5000);
    await flush(card);
    expect(live(card)).toBe("");
    const finished = await setup({ timer: finishedTimer(), settings });
    expect(live(finished.card)).toBe("");
  });

  it("does not repeat the pre-warning after an extension, but announces the next end", async () => {
    const extra = { prewarn_minutes: 5, extra_minutes: 10 };
    const callWS = vi.fn().mockResolvedValue({ timer: timer({ minutes: 10, ends_at: "2026-11-13T09:40:00+00:00" }) });
    const { card, push } = await setup({ timer: timer(), settings: extra, callWS });
    await vi.advanceTimersByTimeAsync(1_500_000);
    await flush(card);
    expect(live(card)).toBe("5 minutes left: Stap a");
    await vi.advanceTimersByTimeAsync(300_000);
    await flush(card);
    expect(live(card)).toBe("Time is up: Stap a");
    await click(card, act("extend", "row"));
    await push(
      timerPayload([parent([sub("a")])], {
        timer: timer({ minutes: 10, ends_at: "2026-11-13T10:10:00+00:00" }),
        settings: extra,
      }),
    );
    await vi.advanceTimersByTimeAsync(305_000);
    await flush(card);
    expect(live(card)).toBe("");
    await vi.advanceTimersByTimeAsync(300_000);
    await flush(card);
    expect(live(card)).toBe("Time is up: Stap a");
  });

  it("says 'Nog 1 minuut' in Dutch for one minute", async () => {
    const { card } = await setup({
      timer: timer(),
      settings: { prewarn_minutes: 1, extra_minutes: null },
      language: "nl",
    });
    await vi.advanceTimersByTimeAsync(1_740_000);
    await flush(card);
    expect(live(card)).toBe("Nog 1 minuut: Stap a");
  });

  it("the countdown itself is not a live region", async () => {
    const { card } = await setup({ timer: timer() });
    for (const countdown of root(card).querySelectorAll(".countdown")) {
      expect(countdown.getAttribute("aria-live")).toBe("off");
      expect(countdown.getAttribute("role")).toBe("timer");
    }
  });
});

describe("texts and accessibility", () => {
  it("speaks Dutch", async () => {
    const { card } = await setup({ timer: finishedTimer(), settings: { prewarn_minutes: null, extra_minutes: 5 }, language: "nl" });
    expect(text(card, `${rowOf()} .timer-state`)).toBe("Tijd is om");
    expect(text(card, act("done", "row"))).toContain("Klaar");
    expect(text(card, act("extend", "row"))).toBe("+5 min");
    expect(text(card, act("not_yet", "row"))).toBe("Nog niet");
    expect(qb(card, "[data-timer-settings-button]").getAttribute("aria-label")).toBe("Timerinstellingen");
  });

  it("gives every timer button an accessible name and a tooltip", async () => {
    const { card } = await setup({ timer: timer() });
    for (const button of root(card).querySelectorAll<HTMLButtonElement>(".timer-btn, .timer-start")) {
      expect(button.getAttribute("aria-label")).toBeTruthy();
      expect(button.getAttribute("title")).toBeTruthy();
      expect(button.tabIndex).toBe(0);
    }
  });

  it("names the group of buttons when time is up", async () => {
    const { card } = await setup({ timer: finishedTimer() });
    expect(q(card, `${rowOf()} .timer-actions`).getAttribute("aria-label")).toBe("Time is up: Stap a");
  });

  it("switches the controls to the new child when the entity changes", async () => {
    const { card } = await setup({ timer: timer() });
    await click(card, act("stop", "row"));
    card.setConfig({ type: "custom:magister-homework-card", entity: "todo.other_homework" });
    await flush(card);
    expect(has(card, ".timer-bar")).toBe(false);
    expect(has(card, ".timer-panel")).toBe(false);
  });

  it("does not keep a confirmation when the card goes read-only", async () => {
    const { card, connection } = await setup({ timer: timer(), subtasks: [sub("a"), sub("b", { minutes: 15 })] });
    await click(card, `[data-timer-start="${SUB_B}"]`);
    expect(has(card, ".timer-confirm")).toBe(true);
    connection.emit("disconnected");
    await flush(card);
    expect(has(card, ".timer-confirm")).toBe(false);
  });
});
