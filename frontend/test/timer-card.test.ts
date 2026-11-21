import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../src/index";
import { timerConfigFromForm, timerEditorSchema, timerFormData } from "../src/timer-card-editor";
import type { MagisterTimerCardEditor } from "../src/timer-card-editor";
import { MagisterTimerCard, normalizeTimerConfig } from "../src/timer-card";
import { TIMER } from "../src/timer-controller";
import { TRANSLATIONS } from "../src/translations";
import type { HomeworkPayload, StudyTimer, TimerSettings } from "../src/types";
import { ENTITY, FakeConnection, makeHass, wsError } from "./helpers";
import {
  NO_EXTRA,
  PARENT,
  SUB_A,
  finishedTimer,
  parent,
  pausedTimer,
  sub,
  timer,
  timerPayload,
} from "./timer-fixtures";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
  vi.setSystemTime(new Date("2026-11-13T09:30:00Z"));
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.useRealTimers();
});

async function flush(card: MagisterTimerCard): Promise<void> {
  for (let round = 0; round < 4; round++) {
    await Promise.resolve();
    await card.updateComplete;
  }
}

interface Setup {
  config?: Record<string, unknown>;
  timer?: StudyTimer | null;
  settings?: TimerSettings;
  language?: string;
  callWS?: ReturnType<typeof vi.fn>;
  payload?: HomeworkPayload;
  push?: boolean;
}

async function setup(options: Setup = {}) {
  const connection = new FakeConnection();
  const callWS = options.callWS ?? vi.fn();
  const card = document.createElement("magister-timer-card") as MagisterTimerCard;
  card.setConfig({ type: "custom:magister-timer-card", entity: ENTITY, ...options.config });
  card.hass = makeHass(connection, callWS, options.language ?? "en");
  document.body.append(card);
  await flush(card);
  if (options.push !== false) {
    connection.push(
      options.payload ??
        timerPayload([parent([sub("a", { progress: 25, last_partial: 25 }), sub("b")])], {
          timer: options.timer ?? null,
          settings: options.settings ?? NO_EXTRA,
        }),
    );
    await flush(card);
  }
  return { card, connection, callWS };
}

const root = (card: MagisterTimerCard): ShadowRoot => {
  if (!card.shadowRoot) throw new Error("no shadow root");
  return card.shadowRoot;
};
const q = (card: MagisterTimerCard, selector: string): HTMLElement => {
  const found = root(card).querySelector<HTMLElement>(selector);
  if (!found) throw new Error(`no ${selector}`);
  return found;
};
const qb = q as (card: MagisterTimerCard, selector: string) => HTMLButtonElement;
const has = (card: MagisterTimerCard, selector: string): boolean => root(card).querySelector(selector) !== null;
const text = (card: MagisterTimerCard, selector: string): string => q(card, selector).textContent.replace(/\s+/g, " ").trim();
const act = (name: string): string => `[data-timer-act="${name}"][data-timer-uid="${SUB_A}"][data-timer-where="card"]`;
async function click(card: MagisterTimerCard, selector: string): Promise<void> {
  qb(card, selector).click();
  await flush(card);
}
const T = TRANSLATIONS.en.timer;

describe("registration and config", () => {
  it("is a second custom element in the same bundle, with its own card picker entry", () => {
    expect(customElements.get("magister-timer-card")).toBe(MagisterTimerCard);
    expect(customElements.get("magister-homework-card")).toBeDefined();
    expect(customElements.get("magister-timer-card-editor")).toBeDefined();
    expect(window.customCards).toContainEqual(
      expect.objectContaining({ type: "magister-timer-card", name: "Magister Study timer", preview: true }),
    );
    expect(window.customCards?.filter((card) => card.type === "magister-timer-card")).toHaveLength(1);
  });

  it("normalizes the config: show_when_idle defaults to true", () => {
    expect(normalizeTimerConfig({ entity: "todo.a" })).toEqual({ entity: "todo.a", title: "", show_when_idle: true });
    expect(normalizeTimerConfig({ entity: "todo.a", title: "Timer", show_when_idle: false })).toEqual({
      entity: "todo.a",
      title: "Timer",
      show_when_idle: false,
    });
    expect(normalizeTimerConfig({}).entity).toBe("");
    expect(() => normalizeTimerConfig({ entity: "sensor.a" })).toThrow("todo");
    expect(() => normalizeTimerConfig({ entity: 5 as unknown as string })).toThrow("entity");
    expect(() => normalizeTimerConfig(undefined)).toThrow("Invalid");
  });

  it("offers a stub config with a Magister to-do entity and a card size", () => {
    expect(
      MagisterTimerCard.getStubConfig({
        connection: {} as never,
        callWS: () => Promise.resolve({} as never),
        entities: { "todo.x": { platform: "other" }, "todo.kind": { platform: "magister" } },
      }),
    ).toEqual({ entity: "todo.kind" });
    expect(MagisterTimerCard.getStubConfig()).toEqual({ entity: "" });
  });

  it("asks for an entity, shows loading and load errors", async () => {
    const empty = await setup({ config: { entity: "" }, push: false });
    expect(text(empty.card, ".state")).toBe(TRANSLATIONS.en.choose_entity);
    document.body.innerHTML = "";
    const loading = await setup({ push: false });
    expect(text(loading.card, ".state")).toBe(TRANSLATIONS.en.loading);
    document.body.innerHTML = "";
    const connection = new FakeConnection();
    connection.subscribeMessage = () => Promise.reject(wsError("not_found"));
    const card = document.createElement("magister-timer-card") as MagisterTimerCard;
    card.setConfig({ type: "custom:magister-timer-card", entity: ENTITY });
    card.hass = makeHass(connection);
    document.body.append(card);
    await flush(card);
    expect(text(card, ".state.error")).toBe(TRANSLATIONS.en.not_found);
  });
});

describe("idle", () => {
  it("says no timer is active", async () => {
    const { card } = await setup();
    expect(text(card, ".timer-idle")).toBe("No timer active");
    expect(card.hasAttribute("hidden")).toBe(false);
    expect(card.getCardSize()).toBe(2);
  });

  it("is hidden without a timer when show_when_idle is false, also while loading", async () => {
    const { card, connection } = await setup({ config: { show_when_idle: false }, push: false });
    expect(card.hasAttribute("hidden")).toBe(true);
    expect(root(card).querySelector("ha-card")).toBeNull();
    expect(card.getCardSize()).toBe(0);
    connection.push(timerPayload([parent([sub("a")])], { timer: null }));
    await flush(card);
    expect(card.hasAttribute("hidden")).toBe(true);
    connection.push(timerPayload([parent([sub("a")])], { timer: timer() }));
    await flush(card);
    expect(card.hasAttribute("hidden")).toBe(false);
    expect(has(card, ".tc")).toBe(true);
    connection.push(timerPayload([parent([sub("a")])], { timer: null }));
    await flush(card);
    expect(card.hasAttribute("hidden")).toBe(true);
  });

  it("shows a load error even when hidden when idle", async () => {
    const connection = new FakeConnection();
    connection.subscribeMessage = () => Promise.reject(wsError("unauthorized"));
    const card = document.createElement("magister-timer-card") as MagisterTimerCard;
    card.setConfig({ type: "custom:magister-timer-card", entity: ENTITY, show_when_idle: false });
    card.hass = makeHass(connection);
    document.body.append(card);
    await flush(card);
    expect(card.hasAttribute("hidden")).toBe(false);
    expect(text(card, ".state.error")).toBe(TRANSLATIONS.en.unauthorized);
  });

  it("shows the title as the card header", async () => {
    const { card } = await setup({ config: { title: "Studietimer Kind" } });
    expect((q(card, "ha-card") as unknown as { header: string }).header).toBe("Studietimer Kind");
  });
});

describe("a running timer", () => {
  it("shows the title, subject, label, due day, a large countdown and the state", async () => {
    const { card } = await setup({ timer: timer() });
    expect(text(card, ".tc-title")).toBe("Stap a");
    expect(text(card, ".tc-meta")).toBe("Engels · Proefwerk · Tue 17 Nov");
    expect(text(card, ".big")).toContain("30:00");
    expect(text(card, ".state-name")).toBe("Running");
    expect(card.getCardSize()).toBe(4);
  });

  it("draws the ring from the elapsed share and moves it every second", async () => {
    const { card } = await setup({ timer: timer() });
    const offset = (): number => Number(q(card, ".ring-fill").getAttribute("stroke-dashoffset"));
    const length = Number(q(card, ".ring-fill").getAttribute("stroke-dasharray"));
    expect(offset()).toBeCloseTo(length, 1);
    await vi.advanceTimersByTimeAsync(900_000);
    await flush(card);
    expect(offset()).toBeCloseTo(length / 2, 1);
    expect(text(card, ".big")).toContain("15:00");
  });

  it("shows h:mm:ss from an hour", async () => {
    const { card } = await setup({ timer: timer({ minutes: 90, ends_at: "2026-11-13T11:00:00+00:00" }) });
    expect(text(card, ".big")).toContain("1:30:00");
    expect(q(card, ".big").classList.contains("long")).toBe(true);
  });

  it("has large touch targets for Pause and Stop with visible text", async () => {
    const { card } = await setup({ timer: timer() });
    expect(text(card, act("pause"))).toContain("Pause");
    expect(text(card, act("stop"))).toContain("Stop");
    expect(qb(card, act("pause")).classList.contains("big")).toBe(true);
    expect(has(card, act("extend"))).toBe(false);
    expect(has(card, act("done"))).toBe(false);
  });

  it("pauses and resumes", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: pausedTimer(1800) });
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("pause"));
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "pause" });
    expect(text(card, ".state-name")).toBe("Paused");
    expect(text(card, act("resume"))).toContain("Resume");
    expect(root(card).activeElement).toBe(q(card, act("resume")));
    callWS.mockResolvedValue({ timer: timer() });
    await click(card, act("resume"));
    expect(callWS).toHaveBeenLastCalledWith({ type: TIMER, entity_id: ENTITY, action: "resume" });
    expect(text(card, ".state-name")).toBe("Running");
  });

  it("shows a paused timer with its remainder and without ticking", async () => {
    const { card } = await setup({ timer: pausedTimer(754) });
    expect(text(card, ".big")).toContain("12:34");
    const base = vi.getTimerCount();
    await vi.advanceTimersByTimeAsync(5000);
    expect(text(card, ".big")).toContain("12:34");
    expect(vi.getTimerCount()).toBe(base);
  });

  it("Stop opens the progress panel with the current progress and sends stop with it", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: null });
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("stop"));
    expect(text(card, ".timer-panel-title")).toBe("How far are you?");
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("25");
    await click(card, '.timer-panel [role="radio"]:nth-child(3)');
    await click(card, ".timer-panel .primary");
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "stop", progress: 50 });
    expect(text(card, ".timer-idle")).toBe("No timer active");
    expect(root(card).activeElement).toBe(q(card, ".timer-idle"));
  });

  it("Stop without progress sends stop alone", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: null });
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("stop"));
    await click(card, ".timer-panel .discard");
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "stop" });
  });

  it("Escape closes the panel and returns the focus to Stop", async () => {
    const { card } = await setup({ timer: timer() });
    await click(card, act("stop"));
    q(card, ".timer-panel").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await flush(card);
    expect(has(card, ".timer-panel")).toBe(false);
    expect(root(card).activeElement).toBe(q(card, act("stop")));
  });
});

describe("a finished timer", () => {
  it("shows Time is up with Done and Not yet, and no +x min without the setting", async () => {
    const { card } = await setup({ timer: finishedTimer() });
    expect(text(card, ".state-name")).toBe("Time is up");
    expect(text(card, act("done"))).toContain("Done");
    expect(text(card, act("not_yet"))).toBe("Not yet");
    expect(has(card, act("extend"))).toBe(false);
    expect(text(card, ".big")).toContain("00:00");
    expect(Number(q(card, ".ring-fill").getAttribute("stroke-dashoffset"))).toBeCloseTo(0, 5);
  });

  it("shows +x min only here and only when set", async () => {
    const settings = { prewarn_minutes: null, extra_minutes: 5 };
    const running = await setup({ timer: timer(), settings });
    expect(has(running.card, act("extend"))).toBe(false);
    document.body.innerHTML = "";
    const finished = await setup({ timer: finishedTimer(), settings });
    expect(text(finished.card, act("extend"))).toBe("+5 min");
  });

  it("+x min extends, Done sends done, Not yet opens the panel", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer: timer({ minutes: 5, ends_at: "2026-11-13T09:35:00+00:00" }) });
    const { card } = await setup({ timer: finishedTimer(), settings: { prewarn_minutes: null, extra_minutes: 5 }, callWS });
    await click(card, act("extend"));
    expect(callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "extend" });
    expect(text(card, ".big")).toContain("05:00");
    document.body.innerHTML = "";
    const second = await setup({ timer: finishedTimer(), callWS: vi.fn().mockResolvedValue({ timer: null }) });
    await click(second.card, act("not_yet"));
    expect(second.callWS).not.toHaveBeenCalled();
    expect(has(second.card, ".timer-panel")).toBe(true);
    q(second.card, ".timer-panel").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await flush(second.card);
    expect(root(second.card).activeElement).toBe(q(second.card, act("not_yet")));
    await click(second.card, act("done"));
    expect(second.callWS).toHaveBeenCalledWith({ type: TIMER, entity_id: ENTITY, action: "done" });
  });
});

describe("rights", () => {
  it("turns read-only with an explanation when the backend says the user may not control it", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("not_allowed_for_role"));
    const { card } = await setup({ timer: timer(), callWS });
    expect(has(card, ".read-only")).toBe(false);
    await click(card, act("pause"));
    expect(text(card, ".toast span")).toBe(T.errors.not_allowed_for_role);
    expect(text(card, ".read-only")).toBe(T.read_only);
    expect(qb(card, act("pause")).disabled).toBe(true);
    expect(qb(card, act("stop")).disabled).toBe(true);
    // the timer is still followed
    expect(text(card, ".big")).toContain("30:00");
    // and a new payload keeps showing it
    await vi.advanceTimersByTimeAsync(2000);
    await flush(card);
    expect(text(card, ".big")).toContain("29:58");
    expect(has(card, ".read-only")).toBe(true);
  });

  it("also for a missing control permission", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("unauthorized"));
    const { card } = await setup({ timer: timer(), callWS, language: "nl" });
    await click(card, act("pause"));
    expect(text(card, ".read-only")).toBe(TRANSLATIONS.nl.timer.read_only);
    expect(text(card, ".toast span")).toBe(TRANSLATIONS.nl.timer.errors.unauthorized);
  });

  it("other errors roll back and keep the buttons", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("timer_wrong_state"));
    const { card } = await setup({ timer: timer(), callWS });
    await click(card, act("pause"));
    expect(text(card, ".state-name")).toBe("Running");
    expect(has(card, ".read-only")).toBe(false);
    expect(qb(card, act("pause")).disabled).toBe(false);
    await click(card, ".toast button");
    expect(has(card, ".toast")).toBe(false);
  });

  it("disables the buttons offline and when the data is unavailable", async () => {
    const { card, connection } = await setup({ timer: timer() });
    connection.emit("disconnected");
    await flush(card);
    expect(qb(card, act("pause")).disabled).toBe(true);
    expect(text(card, ".banner")).toBe(TRANSLATIONS.en.offline);
    connection.emit("ready");
    await flush(card);
    expect(qb(card, act("pause")).disabled).toBe(false);
    connection.push(timerPayload([parent([sub("a")])], { timer: timer(), available: false }));
    await flush(card);
    expect(qb(card, act("pause")).disabled).toBe(true);
    expect(text(card, ".banner")).toBe(TRANSLATIONS.en.unavailable);
  });
});

describe("announcements and texts", () => {
  it("has the polite live region and announces the pre-warning and the end", async () => {
    const { card } = await setup({ timer: timer(), settings: { prewarn_minutes: 5, extra_minutes: null } });
    const region = q(card, ".timer-live");
    expect(region.getAttribute("aria-live")).toBe("polite");
    expect(region.textContent.trim()).toBe("");
    await vi.advanceTimersByTimeAsync(1_500_000);
    await flush(card);
    expect(region.textContent.trim()).toBe("5 minutes left: Stap a");
    await vi.advanceTimersByTimeAsync(300_000);
    await flush(card);
    expect(region.textContent.trim()).toBe("Time is up: Stap a");
    expect(text(card, ".state-name")).toBe("Time is up");
  });

  it("speaks Dutch", async () => {
    const { card } = await setup({
      timer: finishedTimer(),
      settings: { prewarn_minutes: null, extra_minutes: 5 },
      language: "nl",
    });
    expect(text(card, ".state-name")).toBe("Tijd is om");
    expect(text(card, act("done"))).toContain("Klaar");
    expect(text(card, act("extend"))).toBe("+5 min");
    expect(text(card, act("not_yet"))).toBe("Nog niet");
    expect(q(card, ".tc").getAttribute("aria-label")).toBe("Studietimer");
  });

  it("names the countdown for a screen reader without a changing label", async () => {
    const { card } = await setup({ timer: timer() });
    const countdown = q(card, ".big");
    expect(countdown.getAttribute("role")).toBe("timer");
    expect(countdown.getAttribute("aria-live")).toBe("off");
    expect(countdown.querySelector(".sr-only")?.textContent).toBe("Stap a: Running: ");
  });

  it("uses the Dutch card texts for the idle state", async () => {
    const { card } = await setup({ language: "nl" });
    expect(text(card, ".timer-idle")).toBe("Geen timer actief");
  });

  it("switches to the new child when the entity changes, and stops ticking when removed", async () => {
    const { card } = await setup({ timer: timer() });
    card.setConfig({ type: "custom:magister-timer-card", entity: "todo.other_homework" });
    await flush(card);
    expect(text(card, ".state")).toBe(TRANSLATIONS.en.loading);
    card.remove();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("works with parent items that have another parent uid (no list needed)", async () => {
    const { card } = await setup({
      payload: timerPayload([], { timer: timer({ subtask: `${PARENT}:sub:zz`, title: "Los" }) }),
    });
    expect(text(card, ".tc-title")).toBe("Los");
    await click(card, `[data-timer-act="stop"]`);
    expect(q(card, '.timer-panel [aria-checked="true"]').textContent.trim()).toBe("0");
  });
});

describe("the editor", () => {
  it("offers entity, title and show_when_idle", () => {
    const schema = timerEditorSchema();
    expect(schema.map((field) => field.name)).toEqual(["entity", "title", "show_when_idle"]);
    expect(schema[0]).toMatchObject({
      required: true,
      selector: { entity: { filter: { domain: "todo", integration: "magister" } } },
    });
    expect(schema[2]?.selector).toHaveProperty("boolean");
  });

  it("maps the form to the config and keeps unknown keys", () => {
    expect(timerFormData({ entity: "todo.a" })).toEqual({ entity: "todo.a", title: "", show_when_idle: true });
    expect(timerFormData({ entity: "todo.a", show_when_idle: false }).show_when_idle).toBe(false);
    const previous = { type: "custom:magister-timer-card", entity: "todo.a", card_mod: { style: "x" } };
    expect(timerConfigFromForm(previous, { entity: "todo.b", title: "Timer", show_when_idle: false })).toEqual({
      ...previous,
      entity: "todo.b",
      title: "Timer",
      show_when_idle: false,
    });
    expect(
      timerConfigFromForm(
        { ...previous, title: "x", show_when_idle: false },
        { entity: "todo.a", title: "  ", show_when_idle: true },
      ),
    ).toEqual(previous);
    expect(timerConfigFromForm({}, { entity: 5 })).toEqual({ type: "custom:magister-timer-card", entity: "" });
  });

  it("renders an ha-form with translated labels and fires config-changed", async () => {
    const editor = document.createElement("magister-timer-card-editor") as MagisterTimerCardEditor;
    document.body.append(editor);
    await editor.updateComplete;
    expect(editor.shadowRoot?.querySelector("ha-form")).toBeNull();
    editor.hass = { language: "nl", connection: {} as never, callWS: () => Promise.resolve({} as never) };
    editor.setConfig({ type: "custom:magister-timer-card", entity: "todo.a" });
    await editor.updateComplete;
    const form = editor.shadowRoot?.querySelector("ha-form") as
      | (HTMLElement & { schema: unknown; data: unknown; computeLabel: (s: { name: string }) => string })
      | null;
    expect(form?.schema).toEqual(timerEditorSchema());
    expect(form?.data).toEqual({ entity: "todo.a", title: "", show_when_idle: true });
    expect(form?.computeLabel({ name: "show_when_idle" })).toBe("Toon de kaart ook zonder actieve timer");
    expect(form?.computeLabel({ name: "title" })).toBe("Titel (optioneel)");
    expect(form?.computeLabel({ name: "unknown" })).toBe("unknown");
    const changes: unknown[] = [];
    editor.addEventListener("config-changed", (event) => {
      changes.push((event as CustomEvent).detail);
    });
    form?.dispatchEvent(
      new CustomEvent("value-changed", { detail: { value: { entity: "todo.a", show_when_idle: false } } }),
    );
    expect(changes).toEqual([
      { config: { type: "custom:magister-timer-card", entity: "todo.a", show_when_idle: false } },
    ]);
  });

  it("is created by the card for the visual editor", () => {
    expect(MagisterTimerCard.getConfigElement().tagName.toLowerCase()).toBe("magister-timer-card-editor");
  });
});
