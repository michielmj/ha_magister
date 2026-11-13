import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../src/index";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { Hass, HomeworkItem, HomeworkPayload } from "../src/types";
import { TODAY, item } from "./fixtures";

const ENTITY = "todo.kind_myschool_homework";

class FakeConnection {
  callback: ((payload: HomeworkPayload) => void) | undefined;
  message: Record<string, unknown> | undefined;
  options: unknown;
  unsubscribe = vi.fn();
  subscribes = 0;
  reject: unknown;
  private readonly listeners = new Map<string, Set<() => void>>();

  subscribeMessage = (
    callback: (payload: HomeworkPayload) => void,
    message: Record<string, unknown>,
    options?: unknown,
  ): Promise<() => void> => {
    this.subscribes++;
    this.callback = callback;
    this.message = message;
    this.options = options;
    // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors -- HA rejects with a plain {code, message} object
    if (this.reject !== undefined) return Promise.reject(this.reject);
    return Promise.resolve(this.unsubscribe);
  };
  addEventListener = (type: string, listener: () => void): void => {
    const set = this.listeners.get(type) ?? new Set();
    set.add(listener);
    this.listeners.set(type, set);
  };
  removeEventListener = (type: string, listener: () => void): void => {
    this.listeners.get(type)?.delete(listener);
  };
  emit(type: string): void {
    this.listeners.get(type)?.forEach((listener) => {
      listener();
    });
  }
  listenerCount(): number {
    return [...this.listeners.values()].reduce((sum, set) => sum + set.size, 0);
  }
  push(payload: HomeworkPayload): void {
    this.callback?.(payload);
  }
}

function makeHass(connection: FakeConnection, callWS: unknown = vi.fn()): Hass {
  return {
    language: "en",
    config: { time_zone: "Europe/Amsterdam" },
    connection: connection as unknown as Hass["connection"],
    callWS: callWS as Hass["callWS"],
  };
}

async function flush(card: MagisterHomeworkCard): Promise<void> {
  await Promise.resolve();
  await card.updateComplete;
  await Promise.resolve();
  await card.updateComplete;
}

async function mount(
  config: Record<string, unknown> = {},
  hass?: Hass,
  connection = new FakeConnection(),
): Promise<{ card: MagisterHomeworkCard; connection: FakeConnection; hass: Hass }> {
  const card = document.createElement("magister-homework-card") as MagisterHomeworkCard;
  card.setConfig({ type: "custom:magister-homework-card", entity: ENTITY, ...config });
  const usedHass = hass ?? makeHass(connection);
  card.hass = usedHass;
  document.body.append(card);
  await flush(card);
  return { card, connection: usedHass.connection as unknown as FakeConnection, hass: usedHass };
}

const root = (card: MagisterHomeworkCard): ShadowRoot => {
  if (!card.shadowRoot) throw new Error("no shadow root");
  return card.shadowRoot;
};
const texts = (card: MagisterHomeworkCard, selector: string): string[] =>
  [...root(card).querySelectorAll(selector)].map((node) => node.textContent.trim());

function payload(items: HomeworkItem[], available = true): HomeworkPayload {
  return { available, items };
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout"] });
  vi.setSystemTime(new Date("2026-11-13T09:30:00Z"));
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.useRealTimers();
});

describe("registration and card API", () => {
  it("registers the card in window.customCards", () => {
    expect(window.customCards).toContainEqual(
      expect.objectContaining({
        type: "magister-homework-card",
        name: "Magister Homework planner",
        preview: true,
      }),
    );
    expect(customElements.get("magister-homework-card")).toBeDefined();
    expect(customElements.get("magister-homework-card-editor")).toBeDefined();
  });

  it("the stub config picks the first Magister to-do entity", async () => {
    const { card } = await mount();
    const ctor = card.constructor as unknown as {
      getStubConfig(hass: unknown): unknown;
      getConfigElement(): HTMLElement;
    };
    const hass = {
      entities: {
        "sensor.x": { platform: "magister" },
        "todo.shopping": { platform: "shopping_list" },
        "todo.a_homework": { platform: "magister" },
        "todo.b_homework": { platform: "magister" },
      },
    };
    expect(ctor.getStubConfig(hass)).toEqual({ entity: "todo.a_homework" });
    expect(ctor.getStubConfig({})).toEqual({ entity: "" });
    expect(ctor.getStubConfig(undefined)).toEqual({ entity: "" });
    expect(ctor.getConfigElement().localName).toBe("magister-homework-card-editor");
  });

  it("estimates its size from the visible items", async () => {
    const { card, connection } = await mount();
    expect(card.getCardSize()).toBe(3);
    connection.push(payload([item({ uid: "a" }), item({ uid: "b" })]));
    await flush(card);
    expect(card.getCardSize()).toBe(6);
    expect(card.getGridOptions()).toMatchObject({ columns: 12 });
  });
});

describe("subscription", () => {
  it("subscribes to the homework list and shows a loading state first", async () => {
    const { card, connection } = await mount();
    expect(connection.message).toEqual({ type: "magister/homework/subscribe", entity_id: ENTITY });
    expect(connection.options).toEqual({ resubscribe: true });
    expect(texts(card, ".state")).toEqual(["Loading…"]);
  });

  it("asks for an entity when none is configured and does not subscribe", async () => {
    const { card, connection } = await mount({ entity: "" });
    expect(connection.subscribes).toBe(0);
    expect(texts(card, ".state")).toEqual(["Choose a Magister homework list in the card settings."]);
  });

  it("unsubscribes when the card is removed and resubscribes when it returns", async () => {
    const { card, connection } = await mount();
    expect(connection.listenerCount()).toBe(2);
    card.remove();
    expect(connection.unsubscribe).toHaveBeenCalledTimes(1);
    expect(connection.listenerCount()).toBe(0);
    document.body.append(card);
    await flush(card);
    expect(connection.subscribes).toBe(2);
  });

  it("unsubscribes at once when removed while the subscribe call is pending", async () => {
    const connection = new FakeConnection();
    const card = document.createElement("magister-homework-card") as MagisterHomeworkCard;
    card.setConfig({ type: "x", entity: ENTITY });
    card.hass = makeHass(connection);
    document.body.append(card);
    card.remove(); // before the subscribe promise resolved
    await flush(card);
    expect(connection.unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("does not resubscribe on every hass update", async () => {
    const { card, connection, hass } = await mount();
    card.hass = { ...hass };
    card.hass = { ...hass };
    await flush(card);
    expect(connection.subscribes).toBe(1);
  });

  it("resubscribes for a new connection object and for another entity", async () => {
    const { card, connection, hass } = await mount();
    const next = new FakeConnection();
    card.hass = { ...hass, connection: next as unknown as Hass["connection"] };
    await flush(card);
    expect(connection.unsubscribe).toHaveBeenCalledTimes(1);
    expect(next.subscribes).toBe(1);

    card.setConfig({ type: "x", entity: "todo.other" });
    await flush(card);
    expect(next.unsubscribe).toHaveBeenCalledTimes(1);
    expect(next.message).toEqual({ type: "magister/homework/subscribe", entity_id: "todo.other" });
  });

  it("keeps the subscription for a config change that keeps the entity", async () => {
    const { card, connection } = await mount();
    card.setConfig({ type: "x", entity: ENTITY, show_past: true });
    await flush(card);
    expect(connection.subscribes).toBe(1);
    expect(connection.unsubscribe).not.toHaveBeenCalled();
  });

  it("shows a banner while the connection is lost and clears it when it is ready again", async () => {
    const { card, connection } = await mount();
    connection.push(payload([item()]));
    await flush(card);
    connection.emit("disconnected");
    await flush(card);
    expect(texts(card, ".banner")).toEqual(["Connection to Home Assistant lost. Reconnecting…"]);
    expect(texts(card, ".subject")).toEqual(["Wiskunde"]);
    connection.emit("ready");
    await flush(card);
    expect(texts(card, ".banner")).toEqual([]);
  });

  it.each([
    ["not_found", "This homework list was not found."],
    ["invalid_format", "This homework list was not found."],
    ["unauthorized", "You have no access to this homework list."],
    ["boom", "The homework could not be loaded."],
  ])("shows an error state for a failed subscribe (%s)", async (code, message) => {
    const connection = new FakeConnection();
    connection.reject = { code };
    const { card } = await mount({}, undefined, connection);
    expect(texts(card, ".state")).toEqual([message]);
  });
});

describe("rendering", () => {
  const items = [
    item({ uid: "t", date: TODAY, subject: "Wiskunde", info_type: 2, label: "Proefwerk", is_test: true, text: "Hoofdstuk 3", lesson_hour: 2 }),
    item({ uid: "m", date: "2026-11-14", subject: "Engels", text: "", lesson_hour: null }),
    item({ uid: "w", date: "2026-11-16", subject: "Duits", cancelled: true, has_attachments: true }),
    item({ uid: "far", date: "2026-11-30", subject: "Te ver" }),
    item({ uid: "done", date: TODAY, subject: "Klaar", completed: true, progress: 100 }),
    item({ uid: "past", date: "2026-11-11", subject: "Gisteren" }),
  ];

  it("groups per day: Today, Tomorrow, weekday + date; hides far, done and past by default", async () => {
    const { card, connection } = await mount();
    connection.push(payload(items));
    await flush(card);
    expect(texts(card, "h4")).toEqual(["Today", "Tomorrow", "Monday, November 16"]);
    expect(texts(card, ".subject")).toEqual(["Wiskunde", "Engels", "Duits"]);
  });

  it("uses Dutch texts for a Dutch locale", async () => {
    const connection = new FakeConnection();
    const hass = { ...makeHass(connection), language: "nl", locale: { language: "nl" } };
    const { card } = await mount({}, hass, connection);
    connection.push(payload(items));
    await flush(card);
    expect(texts(card, "h4")).toEqual(["Vandaag", "Morgen", "maandag 16 november"]);
    expect(texts(card, ".chip")).toEqual(["Proefwerk", "Huiswerk", "Huiswerk"]);
    expect(texts(card, ".badge")).toEqual(["Les vervallen"]);
  });

  it("shows completed items with show_completed and a past section with show_past", async () => {
    const { card, connection } = await mount({ show_completed: true, show_past: true, days_ahead: 30 });
    connection.push(payload(items));
    await flush(card);
    expect(texts(card, "h3.section")).toEqual(["Earlier"]);
    expect(texts(card, "h4")[0]).toBe("Wednesday, November 11");
    expect(texts(card, ".subject")).toEqual(["Gisteren", "Wiskunde", "Klaar", "Engels", "Duits", "Te ver"]);
    const done = root(card).querySelector<HTMLInputElement>('li.done input[type="checkbox"]');
    expect(done?.checked).toBe(true);
  });

  it("translates chips from info_type and emphasises tests", async () => {
    const { card, connection } = await mount();
    connection.push(payload(items));
    await flush(card);
    expect(texts(card, ".chip")).toEqual(["Test", "Homework", "Homework"]);
    expect(root(card).querySelectorAll(".chip.test")).toHaveLength(1);
    expect(root(card).querySelectorAll("li.item.test")).toHaveLength(1);
  });

  it("marks cancelled lessons, attachments and the lesson hour", async () => {
    const { card, connection } = await mount();
    connection.push(payload(items));
    await flush(card);
    expect(texts(card, ".badge")).toEqual(["Lesson cancelled"]);
    expect(texts(card, ".attachments")).toEqual(["Attachments in Magister"]);
    expect(texts(card, ".meta:not(.attachments)")).toEqual(["Period 2", "Period 2"]);
  });

  it("collapses the text and expands it on tap", async () => {
    const { card, connection } = await mount();
    connection.push(payload([items[0] as HomeworkItem]));
    await flush(card);
    const text = root(card).querySelector<HTMLButtonElement>("button.text");
    expect(text?.getAttribute("aria-expanded")).toBe("false");
    text?.click();
    await flush(card);
    expect(root(card).querySelector("button.text")?.getAttribute("aria-expanded")).toBe("true");
    expect(root(card).querySelector("button.text.expanded")).not.toBeNull();
    root(card).querySelector<HTMLButtonElement>("button.text")?.click();
    await flush(card);
    expect(root(card).querySelector("button.text")?.getAttribute("aria-expanded")).toBe("false");
  });

  it("shows the empty state in English and Dutch", async () => {
    const { card, connection } = await mount();
    connection.push(payload([]));
    await flush(card);
    expect(texts(card, ".state")).toEqual(["No homework"]);

    const nlConnection = new FakeConnection();
    const { card: nl } = await mount({}, { ...makeHass(nlConnection), language: "nl" }, nlConnection);
    nlConnection.push(payload([]));
    await flush(nl);
    expect(texts(nl, ".state")).toEqual(["Geen huiswerk 🎉"]);
  });

  it("shows the title", async () => {
    const { card } = await mount({ title: "Anna" });
    expect((root(card).querySelector("ha-card") as unknown as { header: string }).header).toBe("Anna");
  });

  it("greys the last items and disables the controls when Magister is not available", async () => {
    const { card, connection } = await mount();
    connection.push(payload([item()], false));
    await flush(card);
    expect(texts(card, ".banner")[0]).toMatch(/not available/);
    expect(root(card).querySelector(".days.stale")).not.toBeNull();
    expect(root(card).querySelector<HTMLInputElement>('input[type="checkbox"]')?.disabled).toBe(true);
    expect(root(card).querySelector<HTMLButtonElement>(".segment")?.disabled).toBe(true);
    connection.push(payload([item()], true));
    await flush(card);
    expect(root(card).querySelector(".days.stale")).toBeNull();
    expect(texts(card, ".banner")).toEqual([]);
  });

  it("shows only the banner when unavailable and there are no items", async () => {
    const { card, connection } = await mount();
    connection.push(payload([], false));
    await flush(card);
    expect(texts(card, ".banner")).toHaveLength(1);
    expect(texts(card, ".state")).toEqual([]);
  });
});

describe("progress control", () => {
  it("is a radiogroup of five steps, selecting the nearest step", async () => {
    const { card, connection } = await mount();
    connection.push(payload([item({ progress: 40, last_partial: 40 })]));
    await flush(card);
    const group = root(card).querySelector('[role="radiogroup"]');
    expect(group?.getAttribute("aria-label")).toBe("Progress of Wiskunde");
    const radios = [...root(card).querySelectorAll<HTMLButtonElement>('[role="radio"]')];
    expect(radios.map((radio) => radio.textContent.trim())).toEqual(["0", "25", "50", "75", "100"]);
    expect(radios.map((radio) => radio.getAttribute("aria-checked"))).toEqual(["false", "false", "true", "false", "false"]);
    expect(radios.map((radio) => radio.tabIndex)).toEqual([-1, -1, 0, -1, -1]);
    expect(radios[3]?.getAttribute("aria-label")).toBe("75%");
    expect(texts(card, ".percent")).toEqual(["40%"]);
  });

  it("sends set_progress for the tapped step", async () => {
    const callWS = vi.fn().mockResolvedValue({ progress: 75, completed: false });
    const connection = new FakeConnection();
    const { card } = await mount({}, makeHass(connection, callWS), connection);
    connection.push(payload([item({ uid: "u1" })]));
    await flush(card);
    root(card).querySelectorAll<HTMLButtonElement>('[role="radio"]')[3]?.click();
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/set_progress",
      entity_id: ENTITY,
      item: "u1",
      progress: 75,
    });
    await flush(card);
  });

  it("moves with the arrow keys, Home and End", async () => {
    const callWS = vi
      .fn()
      .mockImplementation((message: { progress: number }) =>
        Promise.resolve({ progress: message.progress, completed: message.progress >= 100 }),
      );
    const connection = new FakeConnection();
    const { card } = await mount({}, makeHass(connection, callWS), connection);
    connection.push(payload([item({ uid: "u1", progress: 50, last_partial: 50 })]));
    await flush(card);
    const press = async (key: string): Promise<void> => {
      const selected = root(card).querySelector<HTMLButtonElement>('[aria-checked="true"]');
      selected?.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
      await flush(card);
    };
    await press("ArrowRight");
    expect(callWS).toHaveBeenLastCalledWith(expect.objectContaining({ progress: 75 }));
    await press("End");
    expect(callWS).toHaveBeenLastCalledWith(expect.objectContaining({ progress: 100 }));
    await press("Home");
    expect(callWS).toHaveBeenLastCalledWith(expect.objectContaining({ progress: 0 }));
    await press("ArrowLeft");
    expect(callWS).toHaveBeenCalledTimes(3); // already at 0 in the view: nothing to move to
    await press("x");
    expect(callWS).toHaveBeenCalledTimes(3);
    await flush(card);
  });
});

describe("checkbox, optimistic UI and rollback", () => {
  const setup = async (callWS: unknown, items: HomeworkItem[]) => {
    const connection = new FakeConnection();
    const { card } = await mount({ show_completed: true }, makeHass(connection, callWS), connection);
    connection.push(payload(items));
    await flush(card);
    return { card, connection };
  };
  const checkbox = (card: MagisterHomeworkCard) =>
    root(card).querySelector<HTMLInputElement>('input[type="checkbox"]');
  const checked = (card: MagisterHomeworkCard): string[] =>
    [...root(card).querySelectorAll('[aria-checked="true"]')].map((n) => n.textContent.trim());

  it("ticking sends 100 and shows it before the answer arrives", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const { card } = await setup(callWS, [item({ uid: "u1", progress: 50, last_partial: 50 })]);
    expect(checkbox(card)?.getAttribute("aria-label")).toBe("Mark Wiskunde as done");
    checkbox(card)?.dispatchEvent(new Event("change"));
    expect(callWS).toHaveBeenCalledWith(expect.objectContaining({ item: "u1", progress: 100 }));
    await flush(card);
    expect(checked(card)).toEqual(["100"]); // optimistic
    expect(root(card).querySelector("li.done")).not.toBeNull();
    resolve({ progress: 100, completed: true });
    await flush(card);
    expect(checked(card)).toEqual(["100"]);
  });

  it("unticking sends last_partial as an explicit value", async () => {
    const callWS = vi.fn().mockResolvedValue({ progress: 40, completed: false });
    const { card } = await setup(callWS, [
      item({ uid: "u1", progress: 100, completed: true, last_partial: 40 }),
    ]);
    expect(checkbox(card)?.getAttribute("aria-label")).toBe("Mark Wiskunde as not done");
    checkbox(card)?.dispatchEvent(new Event("change"));
    expect(callWS).toHaveBeenCalledWith(expect.objectContaining({ item: "u1", progress: 40 }));
    await flush(card);
    expect(checked(card)).toEqual(["50"]); // 40 % shown on the nearest step
    expect(texts(card, ".percent")).toEqual(["40%"]);
  });

  it("an item that was just ticked stays visible so it can be unticked", async () => {
    const callWS = vi
      .fn()
      .mockImplementation((message: { progress: number }) =>
        Promise.resolve({ progress: message.progress, completed: message.progress >= 100 }),
      );
    const connection = new FakeConnection();
    const { card } = await mount({}, makeHass(connection, callWS), connection);
    connection.push(payload([item({ uid: "u1", progress: 50, last_partial: 50 })]));
    await flush(card);
    checkbox(card)?.dispatchEvent(new Event("change"));
    await flush(card);
    connection.push(payload([item({ uid: "u1", progress: 100, completed: true, last_partial: 50 })]));
    await flush(card);
    expect(texts(card, ".subject")).toEqual(["Wiskunde"]);
    expect(checkbox(card)?.checked).toBe(true);
    checkbox(card)?.dispatchEvent(new Event("change")); // untick
    expect(callWS).toHaveBeenLastCalledWith(expect.objectContaining({ progress: 50 }));
  });

  it("rolls back and shows an error when saving fails", async () => {
    const callWS = vi.fn().mockRejectedValue({ code: "item_not_found", message: "no" });
    const { card } = await setup(callWS, [item({ uid: "u1", progress: 25, last_partial: 25 })]);
    checkbox(card)?.dispatchEvent(new Event("change"));
    await flush(card);
    expect(checked(card)).toEqual(["25"]);
    expect(checkbox(card)?.checked).toBe(false);
    const toast = root(card).querySelector('[role="alert"]');
    expect(toast?.textContent).toContain("Saving failed. The change was rolled back.");
  });

  it("explains a permission error, and the toast can be dismissed or times out", async () => {
    const callWS = vi.fn().mockRejectedValue({ code: "unauthorized" });
    const { card } = await setup(callWS, [item({ uid: "u1" })]);
    checkbox(card)?.dispatchEvent(new Event("change"));
    await flush(card);
    expect(root(card).querySelector('[role="alert"]')?.textContent).toContain("No permission");
    root(card).querySelector<HTMLButtonElement>(".toast button")?.click();
    await flush(card);
    expect(root(card).querySelector('[role="alert"]')).toBeNull();

    checkbox(card)?.dispatchEvent(new Event("change"));
    await flush(card);
    expect(root(card).querySelector('[role="alert"]')).not.toBeNull();
    vi.advanceTimersByTime(6100);
    await flush(card);
    expect(root(card).querySelector('[role="alert"]')).toBeNull();
  });

  it("a pushed state replaces the optimistic one, also when it differs from the answer", async () => {
    const callWS = vi.fn().mockResolvedValue({ progress: 75, completed: false });
    const { card, connection } = await setup(callWS, [item({ uid: "u1" })]);
    root(card).querySelectorAll<HTMLButtonElement>('[role="radio"]')[3]?.click();
    await flush(card);
    expect(checked(card)).toEqual(["75"]); // answer arrived before the push: kept
    connection.push(payload([item({ uid: "u1", progress: 75, last_partial: 75 })]));
    await flush(card);
    expect(checked(card)).toEqual(["75"]);
    connection.push(payload([item({ uid: "u1", progress: 25, last_partial: 25 })]));
    await flush(card);
    expect(checked(card)).toEqual(["25"]); // changed elsewhere
  });

  it("drops the optimistic value as soon as the matching push is already there", async () => {
    const callWS = vi.fn().mockImplementation(() => {
      connection.push(payload([item({ uid: "u1", progress: 50, last_partial: 50 })]));
      return Promise.resolve({ progress: 50, completed: false });
    });
    const { card, connection } = await setup(callWS, [item({ uid: "u1" })]);
    root(card).querySelectorAll<HTMLButtonElement>('[role="radio"]')[2]?.click();
    await flush(card);
    expect(checked(card)).toEqual(["50"]);
  });

  it("only the last of two quick taps decides; an older failure does not undo it", async () => {
    const calls: { progress: number; resolve: (v: unknown) => void; reject: (e: unknown) => void }[] = [];
    const callWS = vi.fn().mockImplementation(
      (message: { progress: number }) =>
        new Promise((resolve, reject) => {
          calls.push({ progress: message.progress, resolve, reject });
        }),
    );
    const { card } = await setup(callWS, [item({ uid: "u1" })]);
    const radios = root(card).querySelectorAll<HTMLButtonElement>('[role="radio"]');
    radios[1]?.click();
    radios[3]?.click();
    await flush(card);
    expect(checked(card)).toEqual(["75"]);
    calls[0]?.reject({ code: "boom" });
    await flush(card);
    expect(checked(card)).toEqual(["75"]); // the old failure shows a message but keeps the newer tap
    expect(root(card).querySelector('[role="alert"]')).not.toBeNull();
    calls[1]?.resolve({ progress: 75, completed: false });
    await flush(card);
    expect(checked(card)).toEqual(["75"]);
  });

  it("does not send anything while Magister is not available", async () => {
    const callWS = vi.fn();
    const connection = new FakeConnection();
    const { card } = await mount({}, makeHass(connection, callWS), connection);
    connection.push(payload([item({ uid: "u1" })], false));
    await flush(card);
    checkbox(card)?.dispatchEvent(new Event("change"));
    expect(callWS).not.toHaveBeenCalled();
  });
});
