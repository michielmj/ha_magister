import { describe, expect, it } from "vitest";
import {
  addDays,
  applyOverlay,
  filterItems,
  formatDay,
  groupByDay,
  normalizeConfig,
  snapToStep,
  todayIso,
  toggleTarget,
} from "../src/logic";
import { TODAY, item } from "./fixtures";

const options = { showCompleted: false, showPast: false, daysAhead: 7, today: TODAY };

describe("snapToStep", () => {
  it.each([
    [0, 0],
    [12, 0],
    [13, 25],
    [25, 25],
    [37, 25],
    [38, 50],
    [40, 50],
    [62, 50],
    [63, 75],
    [87, 75],
    [88, 100],
    [100, 100],
    [-5, 0],
    [150, 100],
    [Number.NaN, 0],
  ])("%s -> %s", (value, expected) => {
    expect(snapToStep(value)).toBe(expected);
  });
});

describe("toggleTarget (tick / untick)", () => {
  it("ticking an open item sends 100", () => {
    expect(toggleTarget(item({ progress: 50, last_partial: 50 }))).toBe(100);
    expect(toggleTarget(item())).toBe(100);
  });

  it("unticking restores last_partial as an explicit value", () => {
    expect(toggleTarget(item({ completed: true, progress: 100, last_partial: 40 }))).toBe(40);
    expect(toggleTarget(item({ completed: true, progress: 100, last_partial: 0 }))).toBe(0);
  });

  it("never sends 100 or more when unticking, whatever last_partial says", () => {
    expect(toggleTarget(item({ completed: true, progress: 100, last_partial: 100 }))).toBe(99);
    expect(toggleTarget(item({ completed: true, progress: 100, last_partial: -3 }))).toBe(0);
    expect(toggleTarget(item({ completed: true, progress: 100, last_partial: Number.NaN }))).toBe(0);
  });
});

describe("dates", () => {
  it("adds days across month and year ends", () => {
    expect(addDays("2026-11-28", 5)).toBe("2026-12-03");
    expect(addDays("2026-12-30", 3)).toBe("2027-01-02");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });

  it("takes today in the given time zone", () => {
    const instant = new Date("2026-11-13T23:30:00Z");
    expect(todayIso(instant, "Europe/Amsterdam")).toBe("2026-11-14");
    expect(todayIso(instant, "America/New_York")).toBe("2026-11-13");
    expect(todayIso(instant, "Not/AZone")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("formats a day in the language of the user", () => {
    expect(formatDay("2026-11-16", "nl")).toBe("maandag 16 november");
    expect(formatDay("2026-11-16", "en")).toMatch(/Monday/);
    expect(formatDay("kapot", "nl")).toBe("kapot");
  });
});

describe("filterItems", () => {
  const items = [
    item({ uid: "past", date: "2026-11-12" }),
    item({ uid: "today", date: "2026-11-13" }),
    item({ uid: "done", date: "2026-11-13", completed: true, progress: 100 }),
    item({ uid: "edge", date: "2026-11-20" }),
    item({ uid: "far", date: "2026-11-21" }),
    item({ uid: "past-done", date: "2026-11-10", completed: true, progress: 100 }),
  ];
  const uids = (list: ReturnType<typeof filterItems>) => list.map((i) => i.uid);

  it("hides completed and past items and what is beyond days_ahead (that day included)", () => {
    expect(uids(filterItems(items, options))).toEqual(["today", "edge"]);
  });

  it("shows completed items with show_completed", () => {
    expect(uids(filterItems(items, { ...options, showCompleted: true }))).toEqual([
      "today",
      "done",
      "edge",
    ]);
  });

  it("keeps completed items that were ticked in this session", () => {
    expect(uids(filterItems(items, { ...options, keep: new Set(["done", "far"]) }))).toEqual([
      "today",
      "done",
      "edge",
    ]);
  });

  it("shows past days with show_past (completed ones only when also asked)", () => {
    expect(uids(filterItems(items, { ...options, showPast: true }))).toEqual([
      "past",
      "today",
      "edge",
    ]);
    expect(
      uids(filterItems(items, { ...options, showPast: true, showCompleted: true })),
    ).toContain("past-done");
  });

  it("days_ahead 0 is today only; a larger value reaches further", () => {
    expect(uids(filterItems(items, { ...options, daysAhead: 0 }))).toEqual(["today"]);
    expect(uids(filterItems(items, { ...options, daysAhead: 8 }))).toContain("far");
  });
});

describe("groupByDay", () => {
  it("groups per date in date order with today, tomorrow, future and past kinds", () => {
    const groups = groupByDay(
      [
        item({ uid: "c", date: "2026-11-16" }),
        item({ uid: "a", date: "2026-11-13" }),
        item({ uid: "b", date: "2026-11-14" }),
        item({ uid: "p", date: "2026-11-11" }),
        item({ uid: "a2", date: "2026-11-13" }),
      ],
      TODAY,
    );
    expect(groups.map((g) => [g.date, g.kind, g.items.map((i) => i.uid)])).toEqual([
      ["2026-11-11", "past", ["p"]],
      ["2026-11-13", "today", ["a", "a2"]],
      ["2026-11-14", "tomorrow", ["b"]],
      ["2026-11-16", "future", ["c"]],
    ]);
  });

  it("returns nothing for no items", () => {
    expect(groupByDay([], TODAY)).toEqual([]);
  });
});

describe("applyOverlay", () => {
  it("replaces progress and completed of the affected items only", () => {
    const items = [item({ uid: "a" }), item({ uid: "b", progress: 25 })];
    const result = applyOverlay(items, new Map([["a", { progress: 100, completed: true }]]));
    expect(result[0]).toMatchObject({ uid: "a", progress: 100, completed: true });
    expect(result[1]).toBe(items[1]);
    expect(items[0]?.progress).toBe(0);
  });
});

describe("normalizeConfig", () => {
  it("applies the defaults", () => {
    expect(normalizeConfig({ type: "custom:x", entity: "todo.kind_myschool_homework" })).toEqual({
      entity: "todo.kind_myschool_homework",
      show_completed: false,
      show_past: false,
      days_ahead: 7,
      title: "",
    });
  });

  it("keeps valid options and floors days_ahead", () => {
    expect(
      normalizeConfig({
        entity: "todo.a",
        show_completed: true,
        show_past: true,
        days_ahead: 3.8,
        title: "Anna",
      }),
    ).toEqual({ entity: "todo.a", show_completed: true, show_past: true, days_ahead: 3, title: "Anna" });
  });

  it("allows an empty entity (the card asks for one) but rejects wrong ones", () => {
    expect(normalizeConfig({}).entity).toBe("");
    expect(() => normalizeConfig({ entity: "sensor.x" })).toThrow(/todo/);
    expect(() => normalizeConfig({ entity: 5 as unknown as string })).toThrow();
    expect(() => normalizeConfig({ entity: "todo.a", days_ahead: -1 })).toThrow(/days_ahead/);
    expect(() => normalizeConfig({ entity: "todo.a", days_ahead: "7" as unknown as number })).toThrow();
    expect(() => normalizeConfig(undefined)).toThrow();
  });

  it("caps days_ahead", () => {
    expect(normalizeConfig({ entity: "todo.a", days_ahead: 99999 }).days_ahead).toBe(365);
  });
});
