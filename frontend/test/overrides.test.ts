import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyLabelRemovals,
  applyOverrides,
  hasOverrideFields,
  menuActions,
  optimisticOverride,
  overrideFieldsOf,
} from "../src/logic";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { HomeworkItem, LabelOption } from "../src/types";
import { item } from "./fixtures";
import { ENTITY, flush, manual, mount, payload, root, wsError } from "./helpers";

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

const OPTIONS: LabelOption[] = [
  { id: "default_homework", name: "Huiswerk", kind: "homework" },
  { id: "default_test", name: "Proefwerk", kind: "test" },
  { id: "tw", name: "Toetsweek", kind: "test" },
];
const TOETSWEEK = OPTIONS[2] as LabelOption;
const HUISWERK = OPTIONS[0] as LabelOption;

/** A Proefwerk (info type 2). */
const proefwerk = (overrides: Partial<HomeworkItem> = {}): HomeworkItem =>
  item({ uid: "u1", info_type: 2, label: "Proefwerk", is_test: true, ...overrides });

const text = (card: MagisterHomeworkCard, selector: string): string[] =>
  [...root(card).querySelectorAll(selector)].map((node) => node.textContent.trim());
const find = (card: MagisterHomeworkCard, selector: string): HTMLButtonElement => {
  const found = root(card).querySelector<HTMLButtonElement>(selector);
  if (!found) throw new Error(`no ${selector}`);
  return found;
};
const checkbox = (card: MagisterHomeworkCard): HTMLInputElement => {
  const found = root(card).querySelector<HTMLInputElement>('input[type="checkbox"]');
  if (!found) throw new Error("no checkbox");
  return found;
};
const chip = (card: MagisterHomeworkCard) => find(card, "button.chip.magister");
const menuItems = (card: MagisterHomeworkCard): HTMLButtonElement[] => [
  ...root(card).querySelectorAll<HTMLButtonElement>('.menu [role="menuitem"]'),
];
const menuNames = (card: MagisterHomeworkCard): string[] =>
  menuItems(card).map((entry) => entry.textContent.trim());
const key = (target: Element, name: string): void => {
  target.dispatchEvent(new KeyboardEvent("keydown", { key: name, bubbles: true, composed: true }));
};
const active = (card: MagisterHomeworkCard): Element | null => root(card).activeElement;

async function setup(
  items: HomeworkItem[],
  options: { callWS?: unknown; config?: Record<string, unknown>; language?: string } = {},
) {
  const callWS = options.callWS ?? vi.fn().mockResolvedValue({ item: items[0] });
  const { card, connection } = await mount(options.config ?? {}, callWS, options.language);
  connection.push(payload(items, { labels: OPTIONS }));
  await flush(card);
  return { card, connection, callWS: callWS as ReturnType<typeof vi.fn> };
}

describe("the Magister chip is a menu button", () => {
  it("has the menu button attributes and opens a menu without the original's own label", async () => {
    const { card } = await setup([proefwerk()]);
    expect(chip(card).getAttribute("aria-haspopup")).toBe("menu");
    expect(chip(card).getAttribute("aria-expanded")).toBe("false");
    expect(chip(card).textContent.trim()).toBe("Test");
    chip(card).click();
    await flush(card);
    expect(chip(card).getAttribute("aria-expanded")).toBe("true");
    const menu = find(card, ".menu");
    expect(menu.getAttribute("role")).toBe("menu");
    expect(menu.getAttribute("aria-label")).toBe("Change the Magister label of Wiskunde");
    // "Proefwerk" (default_test) is the original's own label: not offered
    expect(menuNames(card)).toEqual(["Huiswerk", "Toetsweek", "Disable"]);
    expect(menuItems(card).map((entry) => entry.getAttribute("aria-label"))).toEqual([
      "Replace with Huiswerk",
      "Replace with Toetsweek",
      "Disable",
    ]);
    expect(text(card, ".menu-heading")).toEqual(["Replace with…"]);
    expect(active(card)).toBe(menuItems(card)[0]);
  });

  it("is a plain chip while the connection is down or Magister is not available", async () => {
    const { card, connection } = await setup([proefwerk()]);
    connection.emit("disconnected");
    await flush(card);
    expect(root(card).querySelector("button.chip")).toBeNull();
    expect(text(card, ".chip")).toEqual(["Test"]);
    connection.emit("ready");
    connection.push(payload([proefwerk()], { available: false, labels: OPTIONS }));
    await flush(card);
    expect(root(card).querySelector("button.chip")).toBeNull();
  });

  it("closes the menu when the connection drops", async () => {
    const { card, connection } = await setup([proefwerk()]);
    chip(card).click();
    await flush(card);
    expect(root(card).querySelector(".menu")).not.toBeNull();
    connection.emit("disconnected");
    await flush(card);
    expect(root(card).querySelector(".menu")).toBeNull();
  });

  it("works with the keyboard: arrows, Home, End, Escape and focus return", async () => {
    const { card } = await setup([proefwerk()]);
    key(chip(card), "ArrowDown");
    await flush(card);
    const items = menuItems(card);
    expect(active(card)).toBe(items[0]);
    key(items[0] as Element, "ArrowDown");
    expect(active(card)).toBe(items[1]);
    key(items[1] as Element, "ArrowDown");
    key(items[2] as Element, "ArrowDown"); // wraps
    expect(active(card)).toBe(items[0]);
    key(items[0] as Element, "ArrowUp"); // wraps back
    expect(active(card)).toBe(items[2]);
    key(items[2] as Element, "Home");
    expect(active(card)).toBe(items[0]);
    key(items[0] as Element, "End");
    expect(active(card)).toBe(items[2]);
    key(items[2] as Element, "Escape");
    await flush(card);
    expect(root(card).querySelector(".menu")).toBeNull();
    expect(active(card)).toBe(chip(card));
    expect(chip(card).getAttribute("aria-expanded")).toBe("false");
    // ArrowUp opens on the last entry; Escape on the chip closes as well
    key(chip(card), "ArrowUp");
    await flush(card);
    expect(active(card)).toBe(menuItems(card).at(-1));
    chip(card).focus();
    key(chip(card), "Escape");
    await flush(card);
    expect(root(card).querySelector(".menu")).toBeNull();
  });

  it("closes on Tab with the focus on the chip, on the chip again, and on an outside click", async () => {
    const { card } = await setup([proefwerk()]);
    chip(card).click();
    await flush(card);
    key(menuItems(card)[0] as Element, "Tab");
    await flush(card);
    expect(root(card).querySelector(".menu")).toBeNull();
    expect(active(card)).toBe(chip(card));
    chip(card).click();
    await flush(card);
    chip(card).click();
    await flush(card);
    expect(root(card).querySelector(".menu")).toBeNull();
    chip(card).click();
    await flush(card);
    // a click inside the menu does not close it; one outside does
    find(card, ".menu").click();
    await flush(card);
    expect(root(card).querySelector(".menu")).not.toBeNull();
    document.body.click();
    await flush(card);
    expect(root(card).querySelector(".menu")).toBeNull();
  });

  it("ignores keys that do nothing in the menu", async () => {
    const { card } = await setup([proefwerk()]);
    key(chip(card), "x");
    chip(card).click();
    await flush(card);
    key(menuItems(card)[0] as Element, "a");
    expect(root(card).querySelector(".menu")).not.toBeNull();
  });

  it("opens one menu at a time", async () => {
    const { card } = await setup([proefwerk(), item({ uid: "u2", subject: "Frans" })]);
    const chips = [...root(card).querySelectorAll<HTMLButtonElement>("button.chip.magister")];
    chips[0]?.click();
    await flush(card);
    chips[1]?.click();
    await flush(card);
    expect(root(card).querySelectorAll(".menu")).toHaveLength(1);
    expect(chips[0]?.getAttribute("aria-expanded")).toBe("false");
    expect(chips[1]?.getAttribute("aria-expanded")).toBe("true");
  });

  it("is Dutch in a Dutch card", async () => {
    const { card } = await setup([proefwerk()], { language: "nl" });
    chip(card).click();
    await flush(card);
    expect(menuNames(card)).toEqual(["Huiswerk", "Toetsweek", "Uitschakelen"]);
    expect(text(card, ".menu-heading")).toEqual(["Vervangen door…"]);
    expect(menuItems(card)[0]?.getAttribute("aria-label")).toBe("Vervangen door Huiswerk");
    expect(chip(card).title).toBe("Magister-label wijzigen");
  });
});

describe("replacing a label", () => {
  const choose = async (card: MagisterHomeworkCard, name: string): Promise<void> => {
    chip(card).click();
    await flush(card);
    const entry = menuItems(card).find((candidate) => candidate.textContent.trim() === name);
    if (!entry) throw new Error(`no menu item ${name}`);
    entry.click();
    await flush(card);
  };

  it("strikes the chip through, shows the replacement and sends set_override", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const { card } = await setup([proefwerk()], { callWS });
    expect(root(card).querySelector("li.test")).not.toBeNull();
    await choose(card, "Huiswerk");
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/set_override",
      entity_id: ENTITY,
      appointment: "u1",
      mode: "replace",
      label: "default_homework",
    });
    // optimistic: struck through, replacement without ×, no test highlight any more
    expect(root(card).querySelector("button.chip s")?.textContent).toBe("Test");
    expect(text(card, "button.chip .sr-only")).toEqual(["replaced"]);
    const replacement = find(card, ".chip.manual");
    expect(replacement.textContent.trim()).toBe("Huiswerk");
    expect(replacement.querySelector("button")).toBeNull();
    expect(replacement.classList.contains("test")).toBe(false);
    expect(root(card).querySelector("li.test")).toBeNull();
    expect(root(card).querySelector(".menu")).toBeNull();
    expect(active(card)).toBe(chip(card)); // the focus returns to the chip
    resolve({
      item: proefwerk({ override: { mode: "replace", label: HUISWERK }, is_test: false }),
    });
    await flush(card);
    // the answer is kept until the push arrives
    expect(root(card).querySelector(".chip.manual")).not.toBeNull();
  });

  it("follows the pushed state, also a later one that restores the original", async () => {
    const replaced = proefwerk({ override: { mode: "replace", label: TOETSWEEK } });
    const { card, connection } = await setup([replaced]);
    expect(text(card, ".chip.manual")).toEqual(["Toetsweek"]);
    expect(find(card, ".chip.manual").classList.contains("test")).toBe(true);
    connection.push(payload([proefwerk()], { labels: OPTIONS }));
    await flush(card);
    expect(root(card).querySelector(".chip.manual")).toBeNull();
    expect(root(card).querySelector("button.chip s")).toBeNull();
  });

  it("rolls back and explains when the backend refuses", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("label_not_found"));
    const { card } = await setup([proefwerk()], { callWS });
    await choose(card, "Huiswerk");
    expect(root(card).querySelector(".chip.manual")).toBeNull();
    expect(root(card).querySelector("button.chip s")).toBeNull();
    expect(root(card).querySelector("li.test")).not.toBeNull();
    expect(root(card).querySelector(".toast")?.textContent).toContain("no longer exists");
  });

  it("shows the generic message for an unknown error", async () => {
    const callWS = vi.fn().mockRejectedValue(new Error("boom"));
    const { card } = await setup([proefwerk()], { callWS });
    await choose(card, "Huiswerk");
    expect(root(card).querySelector(".toast")?.textContent).toContain("Saving failed");
  });

  it("offers the other options and Restore for a replaced chip, and restores", async () => {
    const replaced = proefwerk({ override: { mode: "replace", label: TOETSWEEK } });
    const callWS = vi.fn().mockResolvedValue({ item: proefwerk() });
    const { card } = await setup([replaced], { callWS });
    chip(card).click();
    await flush(card);
    expect(menuNames(card)).toEqual(["Huiswerk", "Disable", "Restore"]);
    menuItems(card)[2]?.click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/set_override",
      entity_id: ENTITY,
      appointment: "u1",
      mode: "clear",
    });
    expect(root(card).querySelector(".chip.manual")).toBeNull();
    expect(root(card).querySelector("li.test")).not.toBeNull();
  });

  it("drops the optimistic state when the answer has no item", async () => {
    const callWS = vi.fn().mockResolvedValue({ item: null });
    const { card } = await setup([proefwerk()], { callWS });
    await choose(card, "Huiswerk");
    expect(root(card).querySelector(".chip.manual")).toBeNull();
    expect(root(card).querySelector(".toast")).toBeNull();
  });

  it("ignores the answer of an older request after a newer one", async () => {
    const resolvers: ((value: unknown) => void)[] = [];
    const callWS = vi.fn().mockImplementation(
      () => new Promise((r) => resolvers.push(r)),
    );
    const { card } = await setup([proefwerk()], { callWS });
    await choose(card, "Huiswerk");
    await choose(card, "Toetsweek");
    expect(text(card, ".chip.manual")).toEqual(["Toetsweek"]);
    resolvers[0]?.({ item: proefwerk() });
    await flush(card);
    expect(text(card, ".chip.manual")).toEqual(["Toetsweek"]);
  });

  it("does nothing while offline", async () => {
    const callWS = vi.fn();
    const { card, connection } = await setup([proefwerk()], { callWS });
    chip(card).click();
    await flush(card);
    const entry = menuItems(card)[0];
    connection.emit("disconnected");
    entry?.click();
    await flush(card);
    expect(callWS).not.toHaveBeenCalled();
  });
});

describe("disabling a label", () => {
  const disabledItem = (overrides: Partial<HomeworkItem> = {}): HomeworkItem =>
    proefwerk({
      override: { mode: "disable" },
      disabled: true,
      completed: true,
      is_test: false,
      progress: 50,
      last_partial: 50,
      ...overrides,
    });

  it("moves the item to the completed ones, struck through, and keeps it for this session", async () => {
    const callWS = vi.fn().mockResolvedValue({ item: disabledItem() });
    const { card, connection } = await setup([proefwerk({ progress: 50 })], { callWS });
    chip(card).click();
    await flush(card);
    menuItems(card).at(-1)?.click(); // Disable
    await flush(card);
    expect(callWS).toHaveBeenCalledWith(
      expect.objectContaining({ mode: "disable", appointment: "u1" }),
    );
    const row = find(card, "li.item");
    expect(row.classList.contains("done")).toBe(true);
    expect(row.classList.contains("disabled")).toBe(true);
    expect(text(card, "button.chip .sr-only")).toEqual(["disabled"]);
    expect(root(card).querySelector(".chip.manual")).toBeNull();
    // visible although "Done" is off: it was just disabled here
    connection.push(payload([disabledItem()], { labels: OPTIONS }));
    await flush(card);
    expect(root(card).querySelector("li.item")).not.toBeNull();
  });

  it("is only listed with the Done switch, with disabled controls and a Restore-only menu", async () => {
    const { card } = await setup([disabledItem()]);
    expect(root(card).querySelector("li.item")).toBeNull();
    find(card, ".switch").click(); // Done
    await flush(card);
    const row = find(card, "li.item");
    expect(row.classList.contains("done")).toBe(true);
    expect(checkbox(card).disabled).toBe(true);
    expect(checkbox(card).checked).toBe(true);
    const segments = [...root(card).querySelectorAll<HTMLButtonElement>(".segment")];
    expect(segments).toHaveLength(5);
    expect(segments.every((segment) => segment.disabled)).toBe(true);
    expect(text(card, ".percent")).toEqual(["50%"]);
    chip(card).click();
    await flush(card);
    expect(menuNames(card)).toEqual(["Restore"]);
  });

  it("restores a disabled item", async () => {
    const callWS = vi.fn().mockResolvedValue({ item: proefwerk({ progress: 50 }) });
    const { card } = await setup([disabledItem()], { callWS, config: { show_completed: true } });
    chip(card).click();
    await flush(card);
    menuItems(card)[0]?.click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith(expect.objectContaining({ mode: "clear" }));
    expect(checkbox(card).disabled).toBe(false);
    expect(checkbox(card).checked).toBe(false);
    expect(root(card).querySelector("li.done")).toBeNull();
    expect(root(card).querySelector("li.test")).not.toBeNull();
  });

  it("keeps an item with a manual label active and offers replacing and restoring", async () => {
    const active = proefwerk({
      override: { mode: "disable" },
      disabled: false,
      is_test: true,
      manual_labels: [manual()],
    });
    const { card } = await setup([active]);
    expect(root(card).querySelector("li.done")).toBeNull();
    expect(checkbox(card).disabled).toBe(false);
    expect(text(card, "button.chip .sr-only")).toEqual(["disabled"]);
    chip(card).click();
    await flush(card);
    expect(menuNames(card)).toEqual(["Huiswerk", "Toetsweek", "Restore"]);
  });

  it("rolls the disable back when saving fails", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("unauthorized"));
    const { card } = await setup([proefwerk()], { callWS });
    chip(card).click();
    await flush(card);
    menuItems(card).at(-1)?.click();
    await flush(card);
    expect(root(card).querySelector("li.disabled")).toBeNull();
    expect(root(card).querySelector(".toast")?.textContent).toContain("no permission");
  });

  it("explains item_disabled when a progress change is refused", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("item_disabled"));
    const { card } = await setup([proefwerk()], { callWS });
    find(card, ".segment:nth-child(3)").click();
    await flush(card);
    expect(root(card).querySelector(".toast")?.textContent).toContain("Restore the Magister label first");
  });
});

describe("logic", () => {
  it("computes the optimistic override state like the backend", () => {
    const test = proefwerk({ manual_labels: [] });
    expect(optimisticOverride(test, { mode: "replace", label: HUISWERK })).toEqual({
      override: { mode: "replace", label: HUISWERK },
      disabled: false,
      is_test: false,
    });
    expect(optimisticOverride(test, { mode: "replace", label: TOETSWEEK }).is_test).toBe(true);
    expect(optimisticOverride(test, { mode: "disable" })).toEqual({
      override: { mode: "disable" },
      disabled: true,
      is_test: false,
    });
    const withManual = proefwerk({ manual_labels: [manual({ kind: "homework" })] });
    expect(optimisticOverride(withManual, { mode: "disable" })).toEqual({
      override: { mode: "disable" },
      disabled: false,
      is_test: false,
    });
    expect(optimisticOverride(withManual, { mode: "replace", label: HUISWERK }).is_test).toBe(false);
    expect(optimisticOverride(withManual, { mode: "clear" })).toEqual({
      override: null,
      disabled: false,
      is_test: true,
    });
    const homework = item({ info_type: 1 });
    expect(optimisticOverride(homework, { mode: "clear" }).is_test).toBe(false);
    expect(optimisticOverride(item({ info_type: null, manual_labels: [manual()] }), { mode: "clear" }).is_test).toBe(true);
    const keepsTest = proefwerk({ manual_labels: [manual()] });
    expect(optimisticOverride(keepsTest, { mode: "disable" }).is_test).toBe(true);
  });

  it("applies overrides and derives completed from progress and disabled", () => {
    const items = [proefwerk({ progress: 100, completed: true }), item({ uid: "b" })];
    const overlay = new Map([["u1", { override: null, disabled: false, is_test: true }]]);
    const result = applyOverrides(items, overlay);
    expect(result[0]?.completed).toBe(true);
    expect(result[1]).toBe(items[1]);
    const disabled = applyOverrides(
      [proefwerk()],
      new Map([["u1", { override: { mode: "disable" } as const, disabled: true, is_test: false }]]),
    );
    expect(disabled[0]?.completed).toBe(true);
    expect(applyOverrides(items, new Map())).toEqual(items);
  });

  it("compares override states", () => {
    const replaced = proefwerk({ override: { mode: "replace", label: HUISWERK } });
    expect(hasOverrideFields(replaced, overrideFieldsOf(replaced))).toBe(true);
    expect(hasOverrideFields(proefwerk(), overrideFieldsOf(proefwerk()))).toBe(true);
    expect(hasOverrideFields(proefwerk(), overrideFieldsOf(replaced))).toBe(false);
    expect(
      hasOverrideFields(replaced, overrideFieldsOf({ ...replaced, override: { mode: "replace", label: TOETSWEEK } })),
    ).toBe(false);
    const disable = proefwerk({ override: { mode: "disable" } });
    expect(hasOverrideFields(disable, overrideFieldsOf(replaced))).toBe(false);
    expect(hasOverrideFields(disable, overrideFieldsOf(disable))).toBe(true);
    expect(hasOverrideFields(replaced, overrideFieldsOf(proefwerk()))).toBe(false);
    expect(hasOverrideFields(proefwerk({ disabled: true }), overrideFieldsOf(proefwerk()))).toBe(false);
  });

  it("offers the menu actions per state", () => {
    const names = (actions: LabelOption[]): string[] => actions.map((option) => option.name);
    expect(names(menuActions(proefwerk(), OPTIONS).replace)).toEqual(["Huiswerk", "Toetsweek"]);
    expect(names(menuActions(item({ info_type: 1 }), OPTIONS).replace)).toEqual(["Proefwerk", "Toetsweek"]);
    expect(names(menuActions(item({ info_type: null, manual_labels: [manual()] }), OPTIONS).replace)).toEqual(
      ["Huiswerk", "Proefwerk", "Toetsweek"],
    );
    expect(menuActions(proefwerk(), OPTIONS)).toMatchObject({ disable: true, restore: false });
    expect(menuActions(proefwerk({ override: { mode: "disable" } }), OPTIONS)).toMatchObject({
      disable: false,
      restore: true,
    });
    expect(menuActions(proefwerk({ disabled: true, override: { mode: "disable" } }), OPTIONS)).toEqual({
      replace: [],
      disable: false,
      restore: true,
    });
  });

  it("disables an item whose last manual label is removed while its Magister label is disabled", () => {
    const base = proefwerk({
      override: { mode: "disable" },
      is_test: true,
      manual_labels: [manual()],
    });
    const result = applyLabelRemovals([base], new Set([`u1\u0000l2`]));
    expect(result[0]).toMatchObject({ disabled: true, completed: true, is_test: false });
    const plain = applyLabelRemovals([{ ...base, override: null }], new Set([`u1\u0000l2`]));
    expect(plain[0]?.disabled).toBeUndefined();
  });
});
