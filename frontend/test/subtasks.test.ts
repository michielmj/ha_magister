import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applySubtaskEdits,
  derivedProgress,
  groupEntries,
  OVERDUE_GROUP,
  parentUid,
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

function sub(id: string, overrides: Partial<Subtask> = {}): Subtask {
  return {
    uid: `${PARENT}:sub:${id}`,
    title: `Stap ${id}`,
    planned: TODAY,
    date: TODAY,
    overdue: false,
    progress: 0,
    completed: false,
    last_partial: 0,
    ...overrides,
  };
}

/** A Proefwerk on Tuesday 17 Nov with subtasks. */
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
    progress: subtasks.length ? progress : 0,
    completed: subtasks.length > 0 && progress >= 100,
    derived: subtasks.length > 0,
    subtasks,
    ...overrides,
  });
}

const OPTIONS = { today: TODAY, daysAhead: 14, showCompleted: false, showPast: false };

const q = (card: MagisterHomeworkCard, selector: string): HTMLElement => {
  const found = root(card).querySelector<HTMLElement>(selector);
  if (!found) throw new Error(`no ${selector}`);
  return found;
};
const qi = q as (card: MagisterHomeworkCard, selector: string) => HTMLInputElement;
const qb = q as (card: MagisterHomeworkCard, selector: string) => HTMLButtonElement;
const qf = q as (card: MagisterHomeworkCard, selector: string) => HTMLFormElement;
const all = (card: MagisterHomeworkCard, selector: string): string[] =>
  [...root(card).querySelectorAll(selector)].map((node) => node.textContent.trim());
const row = (card: MagisterHomeworkCard, id: string): HTMLElement =>
  q(card, `li[data-uid="${PARENT}:sub:${id}"]`);
const type = (input: HTMLInputElement, value: string): void => {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
};

async function setup(
  items: HomeworkItem[],
  options: { callWS?: unknown; config?: Record<string, unknown>; language?: string } = {},
) {
  const callWS = options.callWS ?? vi.fn().mockResolvedValue({});
  const { card, connection } = await mount(options.config ?? {}, callWS, options.language);
  connection.push(payload(items));
  await flush(card);
  return { card, connection, callWS: callWS as ReturnType<typeof vi.fn> };
}

describe("logic", () => {
  it("groups subtasks by their current date, items first", () => {
    const parent = test([sub("a"), sub("b", { date: "2026-11-16", planned: "2026-11-16" })]);
    const groups = groupEntries([parent], { ...OPTIONS, showPast: true });
    expect(groups.map((group) => group.date)).toEqual([TODAY, "2026-11-16", "2026-11-17"]);
    expect(groups[0]?.entries.map((entry) => entry.type)).toEqual(["subtask"]);
    expect(groups[2]?.entries.map((entry) => entry.type)).toEqual(["item"]);
  });

  it("puts overdue subtasks in a group on top, regardless of the past switch", () => {
    const past = test([sub("a", { overdue: true, date: "2026-11-10" }), sub("b")], {
      date: "2026-11-10",
    });
    const groups = groupEntries([past, item({ uid: "x", date: TODAY })], OPTIONS);
    expect(groups[0]?.kind).toBe("overdue");
    expect(groups[0]?.date).toBe(OVERDUE_GROUP);
    expect(groups[0]?.entries).toHaveLength(1);
  });

  it("keeps a just-ticked overdue subtask in the overdue group", () => {
    const parent = test([sub("a", { progress: 100, completed: true, date: "2026-11-10" })], {
      date: "2026-11-10",
    });
    const keep = new Set([`${PARENT}:sub:a`]);
    expect(groupEntries([parent], { ...OPTIONS, keep })[0]?.kind).toBe("overdue");
    expect(groupEntries([parent], OPTIONS)).toEqual([]);
  });

  it("hides other past subtasks unless the past switch is on, and done ones unless completed is on", () => {
    const parent = test([
      sub("a", { completed: true, progress: 100, date: "2026-11-12" }),
      sub("b"),
    ]);
    const dates = (options: object) =>
      groupEntries([parent], { ...OPTIONS, ...options }).map((group) => group.date);
    expect(dates({})).toEqual([TODAY, "2026-11-17"]);
    expect(dates({ showCompleted: true })).toEqual([TODAY, "2026-11-17"]);
    expect(dates({ showCompleted: true, showPast: true })).toEqual(["2026-11-12", TODAY, "2026-11-17"]);
    expect(dates({ keep: new Set([`${PARENT}:sub:a`]) })).toEqual([TODAY, "2026-11-17"]);
  });

  it("skips subtasks of disabled items and those beyond the window", () => {
    const parent = test([sub("a")], { disabled: true });
    const entries = groupEntries([parent], OPTIONS).flatMap((group) => group.entries);
    expect(entries.filter((entry) => entry.type === "subtask")).toEqual([]);
    const far = test([sub("a", { date: "2026-12-30" })], { date: "2026-12-30" });
    expect(groupEntries([far], OPTIONS)).toEqual([]);
  });

  it("derives the mean rounded half up, and edits subtasks optimistically", () => {
    expect(derivedProgress([])).toBe(0);
    expect(derivedProgress([{ progress: 25 }, { progress: 50 }])).toBe(38);
    expect(parentUid(`${PARENT}:sub:a`)).toBe(PARENT);
    expect(parentUid(PARENT)).toBe(PARENT);
    const parent = test([sub("a", { progress: 100, completed: true }), sub("b")]);
    const edited = applySubtaskEdits(
      [parent],
      new Map([
        [`${PARENT}:sub:b`, { title: "Nieuw", planned: "2026-11-16" }],
        [`${PARENT}:sub:a`, { title: "Oud" }],
      ]),
      TODAY,
    )[0];
    expect(edited?.subtasks?.map((s) => [s.title, s.date])).toEqual([
      ["Oud", TODAY],
      ["Nieuw", "2026-11-16"],
    ]);
    const deleted = applySubtaskEdits(
      [parent],
      new Map([[`${PARENT}:sub:b`, { deleted: true }]]),
      TODAY,
    )[0];
    expect(deleted?.progress).toBe(100);
    const none = applySubtaskEdits(
      [test([sub("a")])],
      new Map([[`${PARENT}:sub:a`, { deleted: true }]]),
      TODAY,
    )[0];
    expect(none?.derived).toBe(false);
    expect(applySubtaskEdits([parent], new Map(), TODAY)).toEqual([parent]);
    expect(reflectsEdit(undefined, { deleted: true })).toBe(true);
    expect(reflectsEdit(sub("a"), { deleted: true })).toBe(false);
    expect(reflectsEdit(undefined, { title: "x" })).toBe(true);
    expect(reflectsEdit(sub("a"), { title: "Stap a" })).toBe(true);
    expect(reflectsEdit(sub("a"), { planned: "2026-11-16" })).toBe(false);
  });
});

describe("rendering", () => {
  const items = () => [
    test([
      sub("a", { progress: 100, completed: true, date: TODAY }),
      sub("b", { progress: 50, last_partial: 50, date: TODAY }),
      sub("c", { date: "2026-11-16", planned: "2026-11-16" }),
    ]),
  ];

  it("shows subtask rows on their day with arrow, reference and steps", async () => {
    const { card } = await setup(items(), { config: { show_completed: true } });
    const b = row(card, "b");
    expect(b.querySelector(".arrow")?.textContent).toBe("↳");
    expect(b.querySelector(".sub-title")?.textContent).toBe("Stap b");
    expect(b.querySelector(".ref")?.textContent).toBe("for Test Engels (Tue 17 Nov)");
    expect(b.querySelectorAll('.segments button[role="radio"]')).toHaveLength(5);
    expect(root(card).querySelector("#day-2026-11-16")).not.toBeNull();
    expect(row(card, "a")).not.toBeNull();
  });

  it("marks subtasks created by the AI coach, and only those", async () => {
    const { card } = await setup(
      [
        test([
          sub("a", { created_by: "ai" }),
          sub("b", { created_by: "user" }),
          sub("c"),
        ]),
      ],
      { config: { show_completed: true } },
    );
    const badge = row(card, "a").querySelector(".ai-badge");
    expect(badge?.textContent.trim()).toBe("AI");
    expect(badge?.getAttribute("aria-label")).toBe("Created by AI coach");
    expect(badge?.getAttribute("title")).toBe("Created by AI coach");
    expect(badge?.getAttribute("role")).toBe("img");
    expect(row(card, "a").querySelector(".sub-title")?.textContent).toBe("Stap a");
    expect(row(card, "b").querySelector(".ai-badge")).toBeNull();
    expect(row(card, "c").querySelector(".ai-badge")).toBeNull(); // missing field = user
  });

  it("words the AI marker in Dutch", async () => {
    const { card } = await setup([test([sub("a", { created_by: "ai" })])], {
      language: "nl",
    });
    const badge = row(card, "a").querySelector(".ai-badge");
    expect(badge?.getAttribute("aria-label")).toBe("Aangemaakt door AI-coach");
    expect(badge?.getAttribute("title")).toBe("Aangemaakt door AI-coach");
  });

  it("keeps the AI marker through an optimistic edit", () => {
    const parent = test([sub("a", { created_by: "ai" })]);
    const edited = applySubtaskEdits(
      [parent],
      new Map([[`${PARENT}:sub:a`, { title: "Nieuw" }]]),
      TODAY,
    )[0];
    expect(edited?.subtasks?.[0]?.created_by).toBe("ai");
  });

  it("follows the card language", async () => {
    const { card } = await setup(items(), { language: "nl" });
    expect(row(card, "b").querySelector(".ref")?.textContent).toMatch(/^voor Proefwerk Engels \(di 17 nov\)$/);
    expect(all(card, ".sub-count")).toEqual(["1 van 3 deelstappen"]);
  });

  it("shows the derived item read-only with count, percentage and aria", async () => {
    const { card } = await setup(items(), { config: { days_ahead: 14 } });
    const li = q(card, `li[data-uid="${PARENT}"]`);
    expect(li.querySelector(".segments")).toBeNull();
    const box = li.querySelector<HTMLInputElement>('input[type="checkbox"]');
    expect(box?.disabled).toBe(true);
    expect(li.querySelector(".sub-count")?.textContent).toBe("1 of 3 subtasks");
    expect(li.querySelector(".percent")?.textContent).toContain("50");
    const bar = li.querySelector('[role="progressbar"]');
    expect(bar?.getAttribute("aria-valuenow")).toBe("50");
    expect(bar?.getAttribute("aria-valuetext")).toBe("1 of 3 subtasks, 50%");
    expect(li.querySelector("[data-add-sub]")).not.toBeNull();
  });

  it("shows the overdue group on top with a marker, also with the past switch off", async () => {
    const overdue = test([sub("a", { overdue: true, date: "2026-11-10" })], { date: "2026-11-10" });
    const { card } = await setup([overdue, item({ uid: "x", date: TODAY })]);
    const headings = all(card, "h4");
    expect(headings[0]).toBe("Overdue");
    expect(row(card, "a").classList.contains("overdue")).toBe(true);
    expect(row(card, "a").querySelector(".badge")?.textContent).toBe("Overdue");
    expect(all(card, "h3.section")).toEqual([]);
  });

  it("uses the singular for one subtask", async () => {
    const { card } = await setup([test([sub("a")])]);
    expect(all(card, ".sub-count")).toEqual(["0 of 1 subtask"]);
  });

  it("applies the switches to subtasks", async () => {
    const { card } = await setup(items());
    expect(root(card).querySelector(`li[data-uid="${PARENT}:sub:a"]`)).toBeNull();
    const toggle = [...root(card).querySelectorAll<HTMLButtonElement>("button.switch")];
    toggle[0]?.click();
    await flush(card);
    expect(row(card, "a")).not.toBeNull();
  });

  it("hides the add action on disabled items and while offline or unavailable", async () => {
    const { card, connection } = await setup([test([], { disabled: true })]);
    expect(root(card).querySelector("[data-add-sub]")).toBeNull();
    connection.push(payload([test([sub("a")])], { available: false }));
    await flush(card);
    expect(root(card).querySelector("[data-add-sub]")).toBeNull();
    connection.push(payload([test([sub("a")])]));
    await flush(card);
    expect(root(card).querySelector("[data-add-sub]")).not.toBeNull();
    (card as unknown as { _offline: boolean })._offline = true;
    await flush(card);
    expect(root(card).querySelector("[data-add-sub]")).toBeNull();
  });
});

describe("ticking subtasks", () => {
  it("ticks to 100 and unticks to last_partial, optimistically with the derived value", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const parent = test([sub("a", { progress: 50, last_partial: 50 }), sub("b")]);
    const { card } = await setup([parent], { callWS, config: { show_completed: true } });
    qi(card, `li[data-uid="${PARENT}:sub:a"] input[type="checkbox"]`).click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/set_progress",
      entity_id: ENTITY,
      item: `${PARENT}:sub:a`,
      progress: 100,
    });
    expect(row(card, "a").classList.contains("done")).toBe(true);
    expect(q(card, `li[data-uid="${PARENT}"] .percent`).textContent).toContain("50");
    resolve({ progress: 100, completed: true });
    await flush(card);

    callWS.mockClear();
    callWS.mockResolvedValue({ progress: 50, completed: false });
    qi(card, `li[data-uid="${PARENT}:sub:a"] input[type="checkbox"]`).click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith(expect.objectContaining({ item: `${PARENT}:sub:a`, progress: 50 }));
  });

  it("explains item_has_subtasks and a subtask that is gone", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("item_not_found"));
    const { card } = await setup([test([sub("a")])], { callWS });
    qi(card, `li[data-uid="${PARENT}:sub:a"] input[type="checkbox"]`).click();
    await flush(card);
    expect(q(card, ".toast").textContent).toContain("not found");
    callWS.mockRejectedValue(wsError("item_has_subtasks"));
    qb(card, `li[data-uid="${PARENT}:sub:a"] .segments button:nth-child(3)`).click();
    await flush(card);
    expect(q(card, ".toast").textContent).toContain("follows from its subtasks");
  });

  it("sets a step and rolls back when it fails", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("item_not_found"));
    const { card } = await setup([test([sub("a"), sub("b")])], { callWS });
    qb(card, `li[data-uid="${PARENT}:sub:a"] .segments button:nth-child(4)`).click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith(expect.objectContaining({ progress: 75 }));
    expect(q(card, `li[data-uid="${PARENT}:sub:a"] button[aria-checked="true"]`).textContent).toContain("0");
    expect(q(card, ".toast")).not.toBeNull();
  });
});

describe("adding a subtask", () => {
  const open = async (card: MagisterHomeworkCard): Promise<void> => {
    qb(card, "[data-add-sub]").click();
    await flush(card);
  };

  it("opens a form with the title focused, today as default and the item date as max", async () => {
    const { card } = await setup([test([])]);
    await open(card);
    const title = qi(card, ".subform .sub-title-input");
    expect(root(card).activeElement).toBe(title);
    expect(title.maxLength).toBe(100);
    expect(title.required).toBe(true);
    const date = qi(card, ".subform .sub-date-input");
    expect([date.value, date.min, date.max, date.disabled]).toEqual([TODAY, TODAY, "2026-11-17", false]);
  });

  it("fixes the date to the item date when that is today or past", async () => {
    const { card } = await setup([test([], { date: TODAY })]);
    await open(card);
    const date = qi(card, ".subform .sub-date-input");
    expect([date.value, date.disabled]).toEqual([TODAY, true]);
  });

  it("waits for the answer, then closes the form and focuses the new row", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const { card, connection } = await setup([test([])], { callWS });
    await open(card);
    type(qi(card, ".subform .sub-title-input"), "  H4 woordjes  ");
    qi(card, ".subform .sub-date-input").value = "2026-11-15";
    qi(card, ".subform .sub-date-input").dispatchEvent(new Event("input"));
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/add_subtask",
      entity_id: ENTITY,
      item: PARENT,
      title: "H4 woordjes",
      date: "2026-11-15",
    });
    // not optimistic: the form stays (busy) and no row exists yet
    expect(root(card).querySelector("form.subform")).not.toBeNull();
    expect(root(card).querySelector(".item.subtask")).toBeNull();
    const added = sub("n", { title: "H4 woordjes", planned: "2026-11-15", date: "2026-11-15" });
    connection.push(payload([test([added])]));
    resolve(test([added]));
    await flush(card);
    expect(root(card).querySelector("form.subform")).toBeNull();
    expect(root(card).activeElement).toBe(q(card, `li[data-uid="${PARENT}:sub:n"] input[type="checkbox"]`));
  });

  it("rejects an empty title without calling the backend", async () => {
    const { card, callWS } = await setup([test([])]);
    await open(card);
    type(qi(card, ".subform .sub-title-input"), "   ");
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(callWS).not.toHaveBeenCalled();
    expect(q(card, ".form-error").textContent).toContain("1 to 100");
  });

  it.each([
    ["invalid_date", "Choose a day"],
    ["too_many_subtasks", "at most 20"],
    ["item_disabled", "disabled"],
    ["invalid_format", "1 to 100"],
    ["boom", "Saving failed"],
  ])("shows %s inline and keeps the input", async (code, message) => {
    const callWS = vi.fn().mockRejectedValue(wsError(code));
    const { card } = await setup([test([])], { callWS });
    await open(card);
    type(qi(card, ".subform .sub-title-input"), "Woordjes");
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(q(card, ".form-error").textContent).toContain(message);
    expect(qi(card, ".sub-title-input").value).toBe("Woordjes");
    expect(qb(card, 'button[type="submit"]').disabled).toBe(false);
  });

  it("focuses the add button when the new subtask is not on screen", async () => {
    // an unusual state (a done subtask on a past day, with the switches off) keeps it hidden
    const hidden = sub("n", { progress: 100, completed: true, date: "2026-11-10" });
    const callWS = vi.fn().mockResolvedValue(test([hidden]));
    const { card, connection } = await setup([test([])], { callWS });
    await open(card);
    type(qi(card, ".subform .sub-title-input"), "Later");
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    connection.push(payload([test([hidden], { completed: false, progress: 0 })]));
    await flush(card);
    expect(root(card).querySelector(`li[data-uid="${PARENT}:sub:n"]`)).toBeNull();
    expect(root(card).activeElement).toBe(q(card, "[data-add-sub]"));
  });

  it("cancels with Escape and returns the focus to the add button", async () => {
    const { card } = await setup([test([])]);
    await open(card);
    q(card, ".sub-title-input").dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }),
    );
    await flush(card);
    expect(root(card).querySelector("form.subform")).toBeNull();
    expect(root(card).activeElement).toBe(q(card, "[data-add-sub]"));
  });

  it("cancels with the Cancel button", async () => {
    const { card } = await setup([test([])]);
    await open(card);
    qb(card, ".form-actions .cancel").click();
    await flush(card);
    expect(root(card).querySelector("form.subform")).toBeNull();
  });

  it("closes the form when the card goes read-only", async () => {
    const { card, connection } = await setup([test([])]);
    await open(card);
    connection.push(payload([test([])], { available: false }));
    await flush(card);
    expect(root(card).querySelector("form.subform")).toBeNull();
  });
});

describe("editing and deleting", () => {
  const parent = () => test([sub("a"), sub("b", { date: "2026-11-16", planned: "2026-11-16" })]);

  it("edits title and date optimistically and sends update_subtask", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const { card } = await setup([parent()], { callWS });
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    const title = qi(card, ".subform .sub-title-input");
    expect(title.value).toBe("Stap a");
    expect(root(card).activeElement).toBe(title);
    type(title, "Nieuwe titel");
    const date = qi(card, ".sub-date-input");
    date.value = "2026-11-16";
    date.dispatchEvent(new Event("input"));
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/update_subtask",
      entity_id: ENTITY,
      subtask: `${PARENT}:sub:a`,
      title: "Nieuwe titel",
      date: "2026-11-16",
    });
    expect(row(card, "a").querySelector(".sub-title")?.textContent).toBe("Nieuwe titel");
    expect(root(card).activeElement).toBe(q(card, `[data-edit="${PARENT}:sub:a"]`));
    resolve({});
    await flush(card);
  });

  it("sends only what changed and nothing when nothing changed", async () => {
    const { card, callWS } = await setup([parent()]);
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(callWS).not.toHaveBeenCalled();
    expect(root(card).querySelector("form.subform")).toBeNull();
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    type(qi(card, ".sub-title-input"), "Anders");
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/update_subtask",
      entity_id: ENTITY,
      subtask: `${PARENT}:sub:a`,
      title: "Anders",
    });
  });

  it("rolls back a failed edit and shows the reason inline", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("invalid_date"));
    const { card } = await setup([parent()], { callWS });
    qb(card, `[data-edit="${PARENT}:sub:a"]`).click();
    await flush(card);
    type(qi(card, ".sub-title-input"), "Anders");
    qf(card, "form.subform").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(q(card, ".form-error").textContent).toContain("Choose a day");
    expect(qi(card, ".sub-title-input").value).toBe("Anders");
    qb(card, ".form-actions .cancel").click();
    await flush(card);
    expect(row(card, "a").querySelector(".sub-title")?.textContent).toBe("Stap a");
  });

  it("deletes after a confirm, optimistically, and focuses a neighbour", async () => {
    const callWS = vi.fn().mockResolvedValue({});
    const { card } = await setup([parent()], { callWS, config: { days_ahead: 14 } });
    qb(card, `[data-delete="${PARENT}:sub:a"]`).click();
    await flush(card);
    expect(callWS).not.toHaveBeenCalled();
    expect(root(card).activeElement).toBe(q(card, ".subconfirm .cancel"));
    qb(card, ".subconfirm .danger").click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/delete_subtask",
      entity_id: ENTITY,
      subtask: `${PARENT}:sub:a`,
    });
    expect(root(card).querySelector(`li[data-uid="${PARENT}:sub:a"]`)).toBeNull();
    expect(root(card).activeElement).not.toBe(document.body);
    expect(root(card).activeElement).not.toBeNull();
  });

  it("cancels a delete with the button and with Escape", async () => {
    const { card, callWS } = await setup([parent()]);
    qb(card, `[data-delete="${PARENT}:sub:a"]`).click();
    await flush(card);
    qb(card, ".subconfirm .cancel").click();
    await flush(card);
    expect(root(card).querySelector(".subconfirm")).toBeNull();
    expect(root(card).activeElement).toBe(q(card, `[data-delete="${PARENT}:sub:a"]`));
    qb(card, `[data-delete="${PARENT}:sub:a"]`).click();
    await flush(card);
    q(card, ".subconfirm").dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }),
    );
    await flush(card);
    expect(root(card).querySelector(".subconfirm")).toBeNull();
    expect(callWS).not.toHaveBeenCalled();
  });

  it("brings a deleted row back with a message when the delete fails", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("subtask_not_found"));
    const { card } = await setup([parent()], { callWS });
    qb(card, `[data-delete="${PARENT}:sub:a"]`).click();
    await flush(card);
    qb(card, ".subconfirm .danger").click();
    await flush(card);
    expect(row(card, "a")).not.toBeNull();
    expect(q(card, ".toast").textContent).toContain("not found");
  });

  it("returns to the item's own progress controls when the last subtask goes", async () => {
    const { card, connection } = await setup([test([sub("a")])]);
    connection.push(payload([test([])]));
    await flush(card);
    const li = q(card, `li[data-uid="${PARENT}"]`);
    expect(li.querySelector(".segments")).not.toBeNull();
    expect(li.querySelector<HTMLInputElement>('input[type="checkbox"]')?.disabled).toBe(false);
  });
});
