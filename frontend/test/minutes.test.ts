import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applySubtaskEdits,
  derivedProgress,
  formatMinutes,
  minuteChoices,
  plannedMinutes,
  reflectsEdit,
} from "../src/logic";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { HomeworkItem, Subtask } from "../src/types";
import { TODAY, item } from "./fixtures";
import { ENTITY, flush, mount, payload, root, wsError } from "./helpers";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout"] });
  vi.setSystemTime(new Date("2026-11-13T09:30:00Z"));
  window.localStorage.clear();
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const PARENT = "school.example.net:1:50";
const MONDAY = "2026-11-16";

function sub(id: string, overrides: Partial<Subtask> = {}): Subtask {
  return {
    uid: `${PARENT}:sub:${id}`,
    title: `Stap ${id}`,
    planned: MONDAY,
    date: MONDAY,
    overdue: false,
    progress: 0,
    completed: false,
    last_partial: 0,
    ...overrides,
  };
}

function test(subtasks: Subtask[], overrides: Partial<HomeworkItem> = {}): HomeworkItem {
  const progress = derivedProgress(subtasks);
  return item({
    uid: PARENT,
    date: "2026-11-17",
    due: "2026-11-17T10:00:00+01:00",
    subject: "Engels",
    info_type: 2,
    label: "Proefwerk",
    is_test: true,
    progress,
    completed: subtasks.length > 0 && progress >= 100,
    derived: subtasks.length > 0,
    subtasks,
    ...overrides,
  });
}

const q = (card: MagisterHomeworkCard, selector: string): HTMLElement => {
  const found = root(card).querySelector<HTMLElement>(selector);
  if (!found) throw new Error(`no ${selector}`);
  return found;
};
const qs = q as (card: MagisterHomeworkCard, selector: string) => HTMLSelectElement;
const qi = q as (card: MagisterHomeworkCard, selector: string) => HTMLInputElement;
const qb = q as (card: MagisterHomeworkCard, selector: string) => HTMLButtonElement;
const qf = q as (card: MagisterHomeworkCard, selector: string) => HTMLFormElement;
const row = (card: MagisterHomeworkCard, id: string): HTMLElement =>
  q(card, `li[data-uid="${PARENT}:sub:${id}"]`);
const submit = (card: MagisterHomeworkCard): void => {
  qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
};
const choose = (select: HTMLSelectElement, value: string): void => {
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
};

async function setup(
  items: HomeworkItem[],
  options: {
    callWS?: unknown;
    language?: string;
    dailyMax?: number;
    overrides?: Record<string, number>;
    config?: Record<string, unknown>;
  } = {},
) {
  const callWS = options.callWS ?? vi.fn().mockResolvedValue({});
  const { card, connection } = await mount(options.config ?? {}, callWS, options.language);
  connection.push(
    payload(items, {
      ...(options.dailyMax === undefined ? {} : { dailyMax: options.dailyMax }),
      ...(options.overrides === undefined ? {} : { overrides: options.overrides }),
    }),
  );
  await flush(card);
  return { card, connection, callWS: callWS as ReturnType<typeof vi.fn> };
}

describe("logic", () => {
  it("formats minutes in both languages", () => {
    expect(formatMinutes(30, "en")).toBe("30 min");
    expect(formatMinutes(60, "en")).toBe("1 h");
    expect(formatMinutes(75, "en")).toBe("1 h 15 min");
    expect(formatMinutes(75, "nl")).toBe("1 u 15 min");
    expect(formatMinutes(240, "nl")).toBe("4 u");
  });

  it("keeps an existing value that is not in the list, in order", () => {
    expect(minuteChoices(null)).toEqual([15, 30, 45, 60, 90, 120, 180, 240]);
    expect(minuteChoices(45)).toEqual([15, 30, 45, 60, 90, 120, 180, 240]);
    expect(minuteChoices(20)).toEqual([15, 20, 30, 45, 60, 90, 120, 180, 240]);
    expect(minuteChoices(undefined)).toHaveLength(8);
    expect(minuteChoices(60, 20)).toEqual([15, 20, 30, 45, 60, 90, 120, 180, 240]);
    expect(minuteChoices(20, 20)).toEqual([15, 20, 30, 45, 60, 90, 120, 180, 240]);
    expect(minuteChoices(25, 20)).toHaveLength(10);
  });

  it("counts the subtasks of a cancelled item in the day total", () => {
    const cancelled = test([sub("a", { minutes: 30 })], { cancelled: true });
    expect(plannedMinutes([cancelled]).get(MONDAY)).toBe(30);
  });

  it("sums the minutes per current date, done or not, and skips disabled items", () => {
    const a = test([
      sub("a", { minutes: 30 }),
      sub("b", { minutes: 45, completed: true, progress: 100 }),
      sub("c", { minutes: null }),
      sub("d"),
      sub("e", { minutes: 15, date: "2026-11-15" }),
    ]);
    const off = test([sub("x", { minutes: 90 })], { uid: "other", disabled: true });
    const totals = plannedMinutes([a, off]);
    expect(totals.get(MONDAY)).toBe(75);
    expect(totals.get("2026-11-15")).toBe(15);
    expect(totals.size).toBe(2);
  });

  it("applies and confirms an optimistic change of the estimate, including clearing it", () => {
    const parent = test([sub("a", { minutes: 30 })]);
    const uid = `${PARENT}:sub:a`;
    const set = applySubtaskEdits([parent], new Map([[uid, { minutes: 60 }]]), TODAY)[0];
    expect(set?.subtasks?.[0]?.minutes).toBe(60);
    const cleared = applySubtaskEdits([parent], new Map([[uid, { minutes: null }]]), TODAY)[0];
    expect(cleared?.subtasks?.[0]?.minutes).toBeNull();
    const kept = applySubtaskEdits([parent], new Map([[uid, { title: "x" }]]), TODAY)[0];
    expect(kept?.subtasks?.[0]?.minutes).toBe(30);
    expect(reflectsEdit(sub("a", { minutes: 30 }), { minutes: 30 })).toBe(true);
    expect(reflectsEdit(sub("a", { minutes: 30 }), { minutes: null })).toBe(false);
    expect(reflectsEdit(sub("a"), { minutes: null })).toBe(true);
    expect(reflectsEdit(sub("a", { minutes: null }), { minutes: null })).toBe(true);
  });
});

describe("rows and chips", () => {
  it("shows the estimate and the Ouder chip, next to the AI chip for ai", async () => {
    const { card } = await setup([
      test([
        sub("a", { minutes: 30, created_by: "parent" }),
        sub("b", { minutes: 75, created_by: "ai" }),
        sub("c", { created_by: "user" }),
      ]),
    ]);
    expect(row(card, "a").querySelector(".sub-minutes")?.textContent.trim()).toBe(
      "Estimated time: 30 min",
    );
    expect(row(card, "a").querySelector(".sub-minutes [aria-hidden]")).toBeNull();
    const chip = row(card, "a").querySelector(".parent-badge");
    expect(chip?.textContent.trim()).toBe("Parent");
    expect(chip?.getAttribute("role")).toBe("img");
    expect(chip?.getAttribute("aria-label")).toBe("Created by parent via AI");
    expect(chip?.getAttribute("title")).toBe("Created by parent via AI");
    expect(row(card, "a").querySelector(".ai-badge:not(.parent-badge)")).toBeNull();
    expect(row(card, "b").querySelector(".parent-badge")).toBeNull();
    expect(row(card, "b").querySelector(".ai-badge")?.textContent.trim()).toBe("AI");
    expect(row(card, "b").querySelector(".sub-minutes")?.textContent).toContain("1 h 15 min");
    expect(row(card, "c").querySelector(".sub-minutes")).toBeNull();
    expect(row(card, "c").querySelector(".ai-badge")).toBeNull();
  });

  it("words the chip and the estimate in Dutch", async () => {
    const { card } = await setup([test([sub("a", { minutes: 75, created_by: "parent" })])], {
      language: "nl",
    });
    const chip = row(card, "a").querySelector(".parent-badge");
    expect(chip?.textContent.trim()).toBe("Ouder");
    expect(chip?.getAttribute("aria-label")).toBe("Aangemaakt door ouder via AI");
    expect(chip?.getAttribute("title")).toBe("Aangemaakt door ouder via AI");
    expect(row(card, "a").querySelector(".sub-minutes")?.textContent.trim()).toBe(
      "Geschatte tijd: 1 u 15 min",
    );
  });
});

describe("day total", () => {
  const items = () => [
    test([
      sub("a", { minutes: 30 }),
      sub("b", { minutes: 45, completed: true, progress: 100 }),
      sub("c", { minutes: 15, date: "2026-11-14", planned: "2026-11-14" }),
      sub("d", { date: "2026-11-15", planned: "2026-11-15" }),
    ]),
  ];
  const head = (card: MagisterHomeworkCard, date: string) =>
    root(card).querySelector(`#day-${date}`)?.closest("section")?.querySelector(".planned");

  it("shows the planned time per day, including done subtasks, and nothing for 0", async () => {
    const { card } = await setup(items(), { dailyMax: 90, config: { show_completed: false } });
    expect(head(card, MONDAY)?.textContent.trim()).toBe("± 1 h 15 min planned");
    expect(head(card, MONDAY)?.classList.contains("over")).toBe(false);
    expect(head(card, "2026-11-14")?.textContent.trim()).toBe("± 15 min planned");
    expect(head(card, "2026-11-15")).toBeNull();
    expect(head(card, "2026-11-17")).toBeNull();
    // the heading keeps its own name
    expect(root(card).querySelector(`#day-${MONDAY}`)?.textContent.trim()).toBe("Monday 16 November");
  });

  it("words it in Dutch", async () => {
    const { card } = await setup(items(), { dailyMax: 90, language: "nl" });
    expect(head(card, MONDAY)?.textContent.trim()).toBe("± 1 u 15 min gepland");
  });

  it("warns above the daily maximum, with an accessible text", async () => {
    const { card } = await setup(items(), { dailyMax: 60 });
    const total = head(card, MONDAY);
    expect(total?.classList.contains("over")).toBe(true);
    expect(total?.textContent).toContain("± 1 h 15 min planned");
    expect(total?.querySelector(".sr-only")?.textContent).toBe(", over daily maximum (1 h)");
    expect(total?.getAttribute("title")).toBe("over daily maximum (1 h)");
    expect(total?.querySelector("[aria-hidden]")?.textContent.trim()).toBe("⚠");
    const visible = [...(total?.querySelectorAll("[aria-hidden]") ?? [])].map((e) => e.textContent.trim());
    expect(visible).toEqual(["⚠", "/ max 1 h"]);
    expect(head(card, "2026-11-14")?.classList.contains("over")).toBe(false);
  });

  it("warns in Dutch and does not warn at exactly the maximum", async () => {
    const { card } = await setup(items(), { dailyMax: 75, language: "nl" });
    expect(head(card, MONDAY)?.classList.contains("over")).toBe(false);
    const { card: second } = await setup(items(), { dailyMax: 60, language: "nl" });
    expect(head(second, MONDAY)?.querySelector(".sr-only")?.textContent).toBe(
      ", boven dagmaximum (1 u)",
    );
    expect(head(second, MONDAY)?.textContent).toContain("/ max 1 u");
  });

  it("shows no warning when the backend sends no maximum", async () => {
    const { card } = await setup(items());
    expect(head(card, MONDAY)?.classList.contains("over")).toBe(false);
  });

  it("uses the override of a day as the effective maximum, with an accessible hint", async () => {
    const { card } = await setup(items(), { dailyMax: 90, overrides: { [MONDAY]: 60 } });
    const total = head(card, MONDAY);
    expect(total?.classList.contains("over")).toBe(true);
    expect(total?.classList.contains("adjusted")).toBe(true);
    const visible = [...(total?.querySelectorAll("[aria-hidden]") ?? [])].map((e) => e.textContent.trim());
    expect(visible).toEqual(["⚠", "/ max 1 h (adjusted)"]);
    expect(total?.querySelector(".sr-only")?.textContent).toBe(", over adjusted daily maximum (1 h)");
    expect(total?.getAttribute("title")).toBe("over adjusted daily maximum (1 h)");
    expect(total?.getAttribute("class")).toBe("planned over adjusted");
    // another day keeps the normal maximum and has no hint
    const other = head(card, "2026-11-14");
    expect(other?.classList.contains("adjusted")).toBe(false);
    expect(other?.querySelector(".sr-only")).toBeNull();
    expect(other?.textContent).not.toContain("max");
  });

  it("a raised maximum removes the warning and still says it was adjusted", async () => {
    const { card } = await setup(items(), { dailyMax: 60, overrides: { [MONDAY]: 120 } });
    const total = head(card, MONDAY);
    expect(total?.classList.contains("over")).toBe(false);
    expect(total?.classList.contains("adjusted")).toBe(true);
    expect(total?.textContent).toContain("± 1 h 15 min planned");
    expect(total?.textContent).toContain("/ max 2 h (adjusted)");
    expect(total?.textContent).not.toContain("⚠");
    expect(total?.querySelector(".sr-only")?.textContent).toBe(", adjusted daily maximum (2 h)");
    expect(total?.getAttribute("title")).toBe("adjusted daily maximum (2 h)");
  });

  it("shows no adjusted marker when the override equals the normal maximum", async () => {
    const { card } = await setup(items(), { dailyMax: 60, overrides: { [MONDAY]: 60 } });
    const total = head(card, MONDAY);
    expect(total?.classList.contains("adjusted")).toBe(false);
    expect(total?.classList.contains("over")).toBe(true);
    expect(total?.textContent).not.toContain("adjusted");
    expect(total?.querySelector(".sr-only")?.textContent).toBe(", over daily maximum (1 h)");
    const { card: roomy } = await setup(items(), { dailyMax: 120, overrides: { [MONDAY]: 120 } });
    const plain = head(roomy, MONDAY);
    expect(plain?.classList.contains("adjusted")).toBe(false);
    expect(plain?.querySelector(".sr-only")).toBeNull();
    expect(plain?.getAttribute("title")).toBeNull();
  });

  it("does not warn at exactly the overridden maximum, and warns above zero", async () => {
    const { card } = await setup(items(), { dailyMax: 30, overrides: { [MONDAY]: 75, "2026-11-14": 0 } });
    expect(head(card, MONDAY)?.classList.contains("over")).toBe(false);
    expect(head(card, "2026-11-14")?.classList.contains("over")).toBe(true);
    expect(head(card, "2026-11-14")?.textContent).toContain("/ max 0 min");
  });

  it("words the hint in Dutch and works without a normal maximum", async () => {
    const { card } = await setup(items(), { overrides: { [MONDAY]: 60 }, language: "nl" });
    const total = head(card, MONDAY);
    expect(total?.querySelector(".sr-only")?.textContent).toBe(
      ", boven aangepast dagmaximum (1 u)",
    );
    expect(total?.textContent).toContain("/ max 1 u (aangepast)");
    expect(head(card, "2026-11-14")?.classList.contains("over")).toBe(false);
  });

  it("shows no total for an overridden day without planned minutes", async () => {
    const { card } = await setup(items(), {
      dailyMax: 90,
      overrides: { "2026-11-15": 15, "2026-11-17": 30, "2026-12-01": 30 },
    });
    expect(head(card, "2026-11-15")).toBeNull();
    expect(head(card, "2026-11-17")).toBeNull();
    expect(head(card, MONDAY)?.classList.contains("adjusted")).toBe(false);
  });

  it("follows an optimistic change of the estimate", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const { card } = await setup(items(), { callWS, dailyMax: 90 });
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    choose(qs(card, ".sub-minutes-input"), "60");
    submit(card);
    await flush(card);
    expect(head(card, MONDAY)?.textContent).toContain("± 1 h 45 min planned");
    expect(head(card, MONDAY)?.classList.contains("over")).toBe(true);
    resolve({});
    await flush(card);
  });

  it("does not show a total on the overdue group", async () => {
    const overdue = test([sub("a", { minutes: 30, overdue: true, date: "2026-11-12" })], {
      date: "2026-11-12",
    });
    const { card } = await setup([overdue], { dailyMax: 15 });
    expect(root(card).querySelector(".planned")).toBeNull();
  });
});

describe("forms", () => {
  it("offers the choices and sends the estimate when adding", async () => {
    const callWS = vi.fn().mockResolvedValue(test([sub("n", { minutes: 45 })]));
    const { card } = await setup([test([])], { callWS });
    qb(card, `[data-add-sub="${PARENT}"]`).click();
    await flush(card);
    const select = qs(card, ".subform .sub-minutes-input");
    expect([...select.options].map((o) => o.value)).toEqual([
      "", "15", "30", "45", "60", "90", "120", "180", "240",
    ]);
    expect(select.options[0]?.textContent.trim()).toBe("—");
    expect(select.value).toBe("");
    expect(root(card).querySelector(".subform label")?.nextElementSibling).not.toBeNull();
    const label = [...root(card).querySelectorAll(".subform label")].find((l) =>
      l.contains(select),
    );
    expect(label?.textContent).toContain("Estimated time");
    const input = qi(card, ".subform .sub-title-input");
    input.value = "Woordjes";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    choose(select, "45");
    submit(card);
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/add_subtask",
      entity_id: ENTITY,
      item: PARENT,
      title: "Woordjes",
      date: TODAY,
      minutes: 45,
    });
  });

  it("leaves minutes out when adding without an estimate", async () => {
    const callWS = vi.fn().mockResolvedValue(test([sub("n")]));
    const { card } = await setup([test([])], { callWS });
    qb(card, `[data-add-sub="${PARENT}"]`).click();
    await flush(card);
    const input = qi(card, ".subform .sub-title-input");
    input.value = "Woordjes";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    submit(card);
    await flush(card);
    expect(callWS.mock.calls[0]?.[0]).not.toHaveProperty("minutes");
  });

  it("shows the current estimate when editing and keeps a value that is not in the list", async () => {
    const { card } = await setup([test([sub("a", { minutes: 20 }), sub("b", { minutes: 60 })])]);
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    const select = qs(card, ".sub-minutes-input");
    expect([...select.options].map((o) => o.value)).toContain("20");
    expect(select.value).toBe("20");
    qb(card, ".form-actions .cancel").click();
    await flush(card);
    qb(card, `[data-edit="${PARENT}:sub:b"]`).click();
    await flush(card);
    expect(qs(card, ".sub-minutes-input").value).toBe("60");
    expect([...qs(card, ".sub-minutes-input").options].map((o) => o.value)).not.toContain("20");
  });

  it("keeps the stored off-list estimate selectable after choosing another", async () => {
    const { card } = await setup([test([sub("a", { minutes: 20 })])]);
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    choose(qs(card, ".sub-minutes-input"), "60");
    await flush(card);
    const select = qs(card, ".sub-minutes-input");
    expect(select.value).toBe("60");
    expect([...select.options].map((o) => o.value)).toContain("20");
  });

  it("sends nothing when the estimate is unchanged, even if it is not in the list", async () => {
    const { card, callWS } = await setup([test([sub("a", { minutes: 20 })])]);
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    submit(card);
    await flush(card);
    expect(callWS).not.toHaveBeenCalled();
  });

  it("changes the estimate optimistically and sends only minutes", async () => {
    const { card, callWS } = await setup([test([sub("a", { minutes: 30 })])]);
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    choose(qs(card, ".sub-minutes-input"), "90");
    submit(card);
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/update_subtask",
      entity_id: ENTITY,
      subtask: `${PARENT}:sub:a`,
      minutes: 90,
    });
    expect(row(card, "a").querySelector(".sub-minutes")?.textContent).toContain("1 h 30 min");
  });

  it("sends null when the estimate is cleared, and the row loses it", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const { card } = await setup([test([sub("a", { minutes: 30 })])], { callWS });
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    choose(qs(card, ".sub-minutes-input"), "");
    submit(card);
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/update_subtask",
      entity_id: ENTITY,
      subtask: `${PARENT}:sub:a`,
      minutes: null,
    });
    expect(row(card, "a").querySelector(".sub-minutes")).toBeNull();
    resolve({});
    await flush(card);
  });

  it("rolls back a failed estimate change and shows the reason inline", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("invalid_minutes"));
    const { card } = await setup([test([sub("a", { minutes: 30 })])], { callWS });
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    choose(qs(card, ".sub-minutes-input"), "120");
    submit(card);
    await flush(card);
    expect(q(card, ".form-error").textContent).toContain("Choose an estimated time");
    expect(qs(card, ".sub-minutes-input").value).toBe("120");
    qb(card, ".form-actions .cancel").click();
    await flush(card);
    expect(row(card, "a").querySelector(".sub-minutes")?.textContent).toContain("30 min");
  });

  it("labels the select in Dutch and disables it while saving", async () => {
    const { card } = await setup([test([])], { language: "nl" });
    qb(card, `[data-add-sub="${PARENT}"]`).click();
    await flush(card);
    const select = qs(card, ".sub-minutes-input");
    const label = [...root(card).querySelectorAll(".subform label")].find((l) => l.contains(select));
    expect(label?.textContent).toContain("Geschatte tijd");
    expect([...select.options].map((o) => o.textContent.trim()).slice(0, 4)).toEqual([
      "—",
      "15 min",
      "30 min",
      "45 min",
    ]);
    expect(select.disabled).toBe(false);
  });
});
