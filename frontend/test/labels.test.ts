import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { Appointment } from "../src/types";
import { TODAY, item } from "./fixtures";
import {
  ENTITY,
  LABELS,
  flush,
  manual,
  mount,
  payload,
  root,
  wsError,
} from "./helpers";

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

const text = (card: MagisterHomeworkCard, selector: string): string[] =>
  [...root(card).querySelectorAll(selector)].map((node) => node.textContent.trim());
const button = (card: MagisterHomeworkCard, selector: string): HTMLButtonElement => {
  const found = root(card).querySelector<HTMLButtonElement>(selector);
  if (!found) throw new Error(`no ${selector}`);
  return found;
};
const subjects = (card: MagisterHomeworkCard): string[] => text(card, ".subject");

describe("header switches", () => {
  const items = [
    item({ uid: "open", subject: "Open" }),
    item({ uid: "done", subject: "Done", completed: true, progress: 100 }),
    item({ uid: "old", subject: "Old", date: "2026-11-11", due: "2026-11-11T10:00:00+01:00" }),
  ];
  const setup = async (config: Record<string, unknown> = {}) => {
    const { card, connection } = await mount(config);
    connection.push(payload(items));
    await flush(card);
    return { card, connection };
  };
  const switches = (card: MagisterHomeworkCard): HTMLButtonElement[] => [
    ...root(card).querySelectorAll<HTMLButtonElement>(".switch"),
  ];

  it("are accessible toggle buttons with tooltips, starting from the config", async () => {
    const { card } = await setup({ show_completed: true });
    const [completed, past] = switches(card);
    expect(completed?.getAttribute("aria-pressed")).toBe("true");
    expect(past?.getAttribute("aria-pressed")).toBe("false");
    expect(completed?.title).toBe("Show completed homework");
    expect(past?.title).toBe("Show earlier days");
    expect(completed?.textContent.trim()).toContain("Done");
    expect(subjects(card)).toEqual(["Open", "Done"]);
  });

  it("toggle the lists and are remembered for the same card", async () => {
    const { card } = await setup();
    expect(subjects(card)).toEqual(["Open"]);
    switches(card)[0]?.click();
    switches(card)[1]?.click();
    await flush(card);
    expect(subjects(card)).toEqual(["Old", "Open", "Done"]);
    expect(switches(card).map((s) => s.getAttribute("aria-pressed"))).toEqual(["true", "true"]);
    expect(Object.keys(window.localStorage)).toHaveLength(1);

    document.body.innerHTML = "";
    const again = await setup();
    expect(subjects(again.card)).toEqual(["Old", "Open", "Done"]);
    switches(again.card)[0]?.click();
    await flush(again.card);
    expect(subjects(again.card)).toEqual(["Old", "Open"]);
  });

  it("are kept apart per card (card_id) and per entity", async () => {
    const first = await setup({ card_id: "aaa" });
    switches(first.card)[0]?.click();
    await flush(first.card);
    const second = await setup({ card_id: "bbb" });
    expect(switches(second.card)[0]?.getAttribute("aria-pressed")).toBe("false");
    const third = await setup({ card_id: "aaa" });
    expect(switches(third.card)[0]?.getAttribute("aria-pressed")).toBe("true");
  });

  it("start again from the config when the config changed", async () => {
    const { card } = await setup();
    switches(card)[0]?.click();
    await flush(card);
    card.setConfig({ type: "custom:magister-homework-card", entity: ENTITY, days_ahead: 3 });
    await flush(card);
    expect(switches(card)[0]?.getAttribute("aria-pressed")).toBe("false");
    card.setConfig({ type: "custom:magister-homework-card", entity: ENTITY });
    await flush(card);
    expect(switches(card)[0]?.getAttribute("aria-pressed")).toBe("true");
  });

  it("work when storage throws on every access", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { card } = await setup();
    switches(card)[0]?.click();
    await flush(card);
    expect(switches(card)[0]?.getAttribute("aria-pressed")).toBe("true");
    expect(subjects(card)).toEqual(["Open", "Done"]);
  });

  it("work when window.localStorage itself throws", async () => {
    const descriptor = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get: () => {
        throw new Error("denied");
      },
    });
    try {
      const { card } = await setup({ show_past: true });
      expect(switches(card)[1]?.getAttribute("aria-pressed")).toBe("true");
      switches(card)[1]?.click();
      await flush(card);
      expect(switches(card)[1]?.getAttribute("aria-pressed")).toBe("false");
    } finally {
      if (descriptor) Object.defineProperty(window, "localStorage", descriptor);
    }
  });

  it("ignore a damaged stored value", async () => {
    const { card } = await setup();
    const key = Object.keys(window.localStorage)[0] ?? "";
    expect(key).toBe("");
    switches(card)[0]?.click();
    await flush(card);
    const stored = Object.keys(window.localStorage)[0] ?? "";
    window.localStorage.setItem(stored, "{oops");
    document.body.innerHTML = "";
    const again = await setup();
    expect(switches(again.card)[0]?.getAttribute("aria-pressed")).toBe("false");
  });
});

describe("language option", () => {
  const items = [item({ uid: "u", date: "2026-11-16", due: "2026-11-16T10:00:00+01:00" })];
  const setup = async (config: Record<string, unknown>, hassLanguage: string) => {
    const { card, connection } = await mount(config, vi.fn(), hassLanguage);
    connection.push(payload(items, { labels: LABELS }));
    await flush(card);
    return card;
  };

  it("forces Dutch in an English Home Assistant", async () => {
    const card = await setup({ language: "nl", days_ahead: 7 }, "en");
    expect(text(card, "h4")).toEqual(["maandag 16 november"]);
    expect(text(card, ".switch")).toEqual(["Afgerond", "Eerder"]);
    expect(button(card, ".add").title).toBe("Label toevoegen");
    expect(text(card, ".chip")).toEqual(["Huiswerk"]);
  });

  it("forces English in a Dutch Home Assistant", async () => {
    const card = await setup({ language: "en" }, "nl");
    expect(text(card, "h4")).toEqual(["Monday 16 November"]);
    expect(text(card, ".switch")).toEqual(["Done", "Earlier"]);
    expect(text(card, ".chip")).toEqual(["Homework"]);
  });

  it("follows Home Assistant for auto and for an unknown value", async () => {
    expect(text(await setup({ language: "auto" }, "nl"), ".switch")).toEqual(["Afgerond", "Eerder"]);
    document.body.innerHTML = "";
    expect(text(await setup({ language: "xx" }, "en"), ".switch")).toEqual(["Done", "Earlier"]);
  });

  it("changes with the config and also translates the dialog", async () => {
    const callWS = vi.fn().mockResolvedValue({ appointments: [] });
    const { card, connection } = await mount({}, callWS, "en");
    connection.push(payload(items, { labels: LABELS }));
    await flush(card);
    card.setConfig({ type: "custom:magister-homework-card", entity: ENTITY, language: "nl" });
    await flush(card);
    button(card, ".add").click();
    await flush(card);
    const dialog = root(card).querySelector("magister-label-dialog");
    expect(dialog?.shadowRoot?.querySelector("h2")?.textContent).toBe("Label toevoegen");
    expect(dialog?.shadowRoot?.textContent).toContain("Geen lessen op deze dag.");
  });
});

describe("manual label chips", () => {
  const withLabels = item({
    uid: "u1",
    subject: "wisB",
    text: "Maak opdracht 3",
    manual_labels: [
      manual({ id: "l2", name: "Toetsweek", kind: "test", note: "H3 + H4" }),
      manual({ id: "l1", name: "Inhalen", kind: "homework", note: "" }),
    ],
    is_test: true,
  });
  const setup = async (
    items = [withLabels],
    callWS: unknown = vi.fn().mockResolvedValue({ item: null }),
    options: { available?: boolean } = {},
  ) => {
    const { card, connection } = await mount({}, callWS);
    connection.push(payload(items, { labels: LABELS, ...options }));
    await flush(card);
    return { card, connection, callWS: callWS as ReturnType<typeof vi.fn> };
  };

  it("renders the Magister chip first, then outlined manual chips, with the note under the text", async () => {
    const { card } = await setup();
    const chips = [...root(card).querySelectorAll(".chip")];
    expect(chips.map((chip) => chip.textContent.replace("×", "").trim())).toEqual([
      "Homework",
      "Toetsweek",
      "Inhalen",
    ]);
    expect(chips.map((chip) => chip.classList.contains("manual"))).toEqual([false, true, true]);
    expect(chips[1]?.classList.contains("test")).toBe(true);
    expect(chips[2]?.classList.contains("test")).toBe(false);
    const main = root(card).querySelector(".main");
    const order = [...(main?.children ?? [])].map((child) => child.className.split(" ")[0]);
    expect(order.indexOf("text")).toBeLessThan(order.indexOf("note"));
    expect(text(card, ".note")).toEqual(["Toetsweek H3 + H4"]);
  });

  it("shows no Magister chip for an item that is only there because of a manual label", async () => {
    const { card } = await setup([
      item({ uid: "m", info_type: null, label: null, text: "", manual_labels: [manual()] }),
    ]);
    expect(text(card, ".chip")).toEqual(["Toetsweek×"]);
  });

  it("only manual chips have a remove button, with an accessible name", async () => {
    const { card } = await setup();
    const removes = [...root(card).querySelectorAll(".chip-remove")];
    expect(removes).toHaveLength(2);
    expect(removes.map((node) => node.getAttribute("aria-label"))).toEqual(["Remove label", "Remove label"]);
    expect(root(card).querySelector(".chip:not(.manual) button")).toBeNull();
  });

  it("asks for confirmation first; cancel and Escape send nothing", async () => {
    const { card, callWS } = await setup();
    button(card, ".chip-remove").click();
    await flush(card);
    expect(root(card).querySelector(".confirm")?.textContent).toContain("Remove label Toetsweek?");
    expect(callWS).not.toHaveBeenCalled();
    button(card, ".confirm .cancel").click();
    await flush(card);
    expect(root(card).querySelector(".confirm")).toBeNull();
    expect(text(card, ".chip")).toHaveLength(3);

    button(card, ".chip-remove").click();
    await flush(card);
    root(card)
      .querySelector(".confirm")
      ?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await flush(card);
    expect(root(card).querySelector(".confirm")).toBeNull();
    expect(callWS).not.toHaveBeenCalled();
  });

  it("removes optimistically, sends remove_label and keeps it gone after the push", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((r) => (resolve = r)));
    const { card, connection } = await setup([withLabels], callWS);
    button(card, ".chip-remove").click();
    await flush(card);
    button(card, ".confirm .danger").click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/remove_label",
      entity_id: ENTITY,
      appointment: "u1",
      label: "l2",
    });
    expect(text(card, ".chip").map((chip) => chip.replace("×", ""))).toEqual(["Homework", "Inhalen"]);
    expect(text(card, ".note")).toEqual([]);
    resolve({ item: null });
    await flush(card);
    expect(text(card, ".chip")).toHaveLength(2);
    connection.push(
      payload([{ ...withLabels, manual_labels: withLabels.manual_labels.slice(1) }], { labels: LABELS }),
    );
    await flush(card);
    expect(text(card, ".chip")).toHaveLength(2);
  });

  it("rolls back and explains the error code when removing fails", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("label_not_on_appointment"));
    const { card } = await setup([withLabels], callWS);
    button(card, ".chip-remove").click();
    await flush(card);
    button(card, ".confirm .danger").click();
    await flush(card);
    expect(text(card, ".chip")).toHaveLength(3);
    expect(root(card).querySelector(".toast")?.textContent).toContain(
      "This label is no longer on the lesson.",
    );
  });

  it.each([
    ["unauthorized", "You have no permission to change labels."],
    ["label_not_found", "This label no longer exists. Choose another label."],
    ["appointment_not_found", "This lesson was not found any more. Choose the day again."],
    ["boom", "Saving failed. The change was rolled back."],
  ])("maps %s to a toast", async (code, message) => {
    const { card } = await setup([withLabels], vi.fn().mockRejectedValue(wsError(code)));
    button(card, ".chip-remove").click();
    await flush(card);
    button(card, ".confirm .danger").click();
    await flush(card);
    expect(root(card).querySelector(".toast")?.textContent).toContain(message);
  });

  it("takes an item out at once when its last manual label goes, and brings it back on failure", async () => {
    let reject: (reason: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(new Promise((_, r) => (reject = r)));
    const only = item({ uid: "m", subject: "Solo", info_type: null, text: "", manual_labels: [manual()] });
    const { card } = await setup([only], callWS);
    button(card, ".chip-remove").click();
    await flush(card);
    button(card, ".confirm .danger").click();
    await flush(card);
    expect(subjects(card)).toEqual([]);
    reject(wsError("unauthorized"));
    await flush(card);
    expect(subjects(card)).toEqual(["Solo"]);
  });

  it("cannot be removed while Magister is not available", async () => {
    const { card } = await setup([withLabels], vi.fn(), { available: false });
    expect(button(card, ".chip-remove").disabled).toBe(true);
  });

  it("cannot be removed while the connection is down", async () => {
    const { card, connection } = await setup();
    connection.emit("disconnected");
    await flush(card);
    expect(button(card, ".chip-remove").disabled).toBe(true);
  });
});

describe("add label dialog", () => {
  const items = [
    item({ uid: "far", date: "2026-11-18", due: "2026-11-18T10:00:00+01:00" }),
    item({ uid: "past", date: "2026-11-11", due: "2026-11-11T10:00:00+01:00" }),
  ];
  const lesson = (overrides: Partial<Appointment> = {}): Appointment => ({
    uid: "school:1:70",
    start: "2026-11-13T09:10:00+01:00",
    end: "2026-11-13T10:00:00+01:00",
    all_day: false,
    lesson_hour: 3,
    subject: "wisB",
    cancelled: false,
    info_type: null,
    manual_labels: [],
    ...overrides,
  });
  const APPOINTMENTS = [
    lesson(),
    lesson({
      uid: "school:1:71",
      start: "2026-11-13T10:00:00+01:00",
      end: "2026-11-13T10:50:00+01:00",
      lesson_hour: 4,
      subject: "netl",
      cancelled: true,
      info_type: 2,
      manual_labels: [manual({ name: "Inhalen" })],
    }),
  ];

  const open = async (
    handler: (message: Record<string, unknown>) => unknown = () => ({ appointments: APPOINTMENTS }),
    labels = LABELS,
  ) => {
    const callWS = vi.fn((message: Record<string, unknown>) => {
      try {
        return Promise.resolve(handler(message));
      } catch (error) {
        // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors -- rethrows what the handler threw
        return Promise.reject(error);
      }
    });
    const { card, connection } = await mount({}, callWS);
    connection.push(payload(items, { labels }));
    await flush(card);
    button(card, ".add").click();
    await flush(card);
    const element = root(card).querySelector("magister-label-dialog");
    if (!element?.shadowRoot) throw new Error("no dialog");
    const inner = element.shadowRoot;
    return { card, connection, callWS, inner, element };
  };
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters -- a typed querySelector
  const field = <T extends Element>(inner: ShadowRoot, selector: string): T => {
    const found = inner.querySelector<T>(selector);
    if (!found) throw new Error(`no ${selector}`);
    return found;
  };
  const save = (inner: ShadowRoot): HTMLButtonElement => field<HTMLButtonElement>(inner, ".primary");
  const choose = async (card: MagisterHomeworkCard, inner: ShadowRoot, lessonIndex = 0, label = "l2") => {
    const radios = inner.querySelectorAll<HTMLInputElement>('input[type="radio"]');
    const radio = radios[lessonIndex];
    if (!radio) throw new Error("no lesson");
    radio.checked = true;
    radio.dispatchEvent(new Event("change", { bubbles: true }));
    const select = field<HTMLSelectElement>(inner, "select");
    select.value = label;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await flush(card);
  };

  it("has a + button only with label options, and not when unavailable or offline", async () => {
    const none = await mount({});
    none.connection.push(payload(items));
    await flush(none.card);
    expect(root(none.card).querySelector(".add")).toBeNull();
    none.connection.push(payload(items, { labels: [] }));
    await flush(none.card);
    expect(root(none.card).querySelector(".add")).toBeNull();
    none.connection.push(payload(items, { labels: LABELS }));
    await flush(none.card);
    expect(root(none.card).querySelector(".add")).not.toBeNull();
    none.connection.emit("disconnected");
    await flush(none.card);
    expect(root(none.card).querySelector(".add")).toBeNull();
    none.connection.emit("ready");
    none.connection.push(payload(items, { labels: LABELS, available: false }));
    await flush(none.card);
    expect(root(none.card).querySelector(".add")).toBeNull();
  });

  it("opens a modal dialog with today's lessons listed with time, hour, subject and labels", async () => {
    const { callWS, inner } = await open();
    const dialog = field<HTMLDialogElement>(inner, "dialog");
    expect(dialog.open).toBe(true);
    expect(dialog.getAttribute("aria-labelledby")).toBe("title");
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/appointments",
      entity_id: ENTITY,
      date: TODAY,
    });
    const lessons = [...inner.querySelectorAll(".lesson")].map((node) =>
      node.textContent.replace(/\s+/g, " ").trim(),
    );
    expect(lessons[0]).toBe("wisB Period 3 09:10–10:00");
    expect(lessons[1]).toBe("netl Period 4 10:00–10:50 Lesson cancelled Test, Inhalen");
    expect(inner.querySelector(".lesson.cancelled")).not.toBeNull();
    const date = field<HTMLInputElement>(inner, 'input[type="date"]');
    expect(date.value).toBe(TODAY);
    expect(date.min).toBe("2026-11-11");
    expect(date.max).toBe("2026-11-20");
    expect(inner.querySelector("small")?.textContent).toBe("Friday 13 November");
  });

  it("lists the labels with their kind and limits the note to 200 characters", async () => {
    const { inner } = await open();
    const options = [...inner.querySelectorAll("option")].map((o) => o.textContent.replace(/\s+/g, " ").trim());
    expect(options).toEqual(["Choose a label", "Huiswerk (homework)", "Toetsweek (test)"]);
    expect(field<HTMLTextAreaElement>(inner, "textarea").maxLength).toBe(200);
  });

  it("loads the lessons of another day", async () => {
    const { card, callWS, inner } = await open((message) =>
      message["date"] === "2026-11-16"
        ? { appointments: [lesson({ uid: "monday", subject: "gs" })] }
        : { appointments: APPOINTMENTS },
    );
    const date = field<HTMLInputElement>(inner, 'input[type="date"]');
    date.value = "2026-11-16";
    date.dispatchEvent(new Event("change", { bubbles: true }));
    await flush(card);
    expect(callWS).toHaveBeenLastCalledWith(expect.objectContaining({ date: "2026-11-16" }));
    expect([...inner.querySelectorAll(".lesson strong")].map((n) => n.textContent)).toEqual(["gs"]);
  });

  it("ignores a late answer for a day that is no longer selected", async () => {
    const pending: ((value: unknown) => void)[] = [];
    const callWS = vi.fn(
      () => new Promise((resolve) => pending.push(resolve)),
    );
    const { card, connection } = await mount({}, callWS);
    connection.push(payload(items, { labels: LABELS }));
    await flush(card);
    button(card, ".add").click();
    await flush(card);
    const inner = root(card).querySelector("magister-label-dialog")?.shadowRoot as ShadowRoot;
    const date = field<HTMLInputElement>(inner, 'input[type="date"]');
    date.value = "2026-11-16";
    date.dispatchEvent(new Event("change", { bubbles: true }));
    await flush(card);
    pending[1]?.({ appointments: [lesson({ uid: "new", subject: "second" })] });
    await flush(card);
    pending[0]?.({ appointments: [lesson({ uid: "old", subject: "first" })] });
    await flush(card);
    expect([...inner.querySelectorAll(".lesson strong")].map((n) => n.textContent)).toEqual(["second"]);
  });

  it("shows an empty state, and the backend error for a day outside the window", async () => {
    const empty = await open(() => ({ appointments: [] }));
    expect(empty.inner.querySelector(".hint")?.textContent).toBe("No lessons on this day.");
    document.body.innerHTML = "";
    const bad = await open(() => {
      throw wsError("invalid_date");
    });
    expect(bad.inner.querySelector(".error")?.textContent).toBe("This day is outside the fetched period.");
    document.body.innerHTML = "";
    const odd = await open(() => {
      throw wsError("weird");
    });
    expect(odd.inner.querySelector(".error")?.textContent).toBe("The lessons could not be loaded.");
  });

  it("needs a lesson and a label before it can save", async () => {
    const { card, inner } = await open();
    expect(save(inner).disabled).toBe(true);
    await choose(card, inner);
    expect(save(inner).disabled).toBe(false);
  });

  it("saves with a trimmed note, closes and returns focus to the + button", async () => {
    const { card, callWS, inner } = await open((message) =>
      message["type"] === "magister/homework/add_label" ? { item: {} } : { appointments: APPOINTMENTS },
    );
    await choose(card, inner, 1, "l1");
    const note = field<HTMLTextAreaElement>(inner, "textarea");
    note.value = "  H3 + H4 \n";
    note.dispatchEvent(new Event("input", { bubbles: true }));
    await flush(card);
    expect(inner.querySelector(".count")?.textContent).toBe("11 of 200 characters");
    field<HTMLFormElement>(inner, "form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(callWS).toHaveBeenLastCalledWith({
      type: "magister/homework/add_label",
      entity_id: ENTITY,
      appointment: "school:1:71",
      label: "l1",
      note: "H3 + H4",
    });
    expect(root(card).querySelector("magister-label-dialog")).toBeNull();
    expect(root(card).activeElement).toBe(root(card).querySelector(".add"));
  });

  it("leaves the note out when it is empty or only spaces", async () => {
    const { card, callWS, inner } = await open();
    await choose(card, inner);
    const note = field<HTMLTextAreaElement>(inner, "textarea");
    note.value = "   ";
    note.dispatchEvent(new Event("input", { bubbles: true }));
    await flush(card);
    save(inner).click();
    field<HTMLFormElement>(inner, "form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    const call = callWS.mock.calls.find((c) => c[0].type === "magister/homework/add_label");
    expect(call?.[0]).toEqual({
      type: "magister/homework/add_label",
      entity_id: ENTITY,
      appointment: "school:1:70",
      label: "l2",
    });
  });

  it.each([
    ["label_exists", "This lesson already has this label."],
    ["invalid_date", "This day is outside the fetched period."],
    ["appointment_not_found", "This lesson was not found any more. Choose the day again."],
    ["label_not_found", "This label no longer exists. Choose another label."],
    ["unauthorized", "You have no permission to change labels."],
    ["weird", "Saving failed."],
  ])("shows %s inline and stays open", async (code, message) => {
    const { card, inner } = await open((request) => {
      if (request["type"] === "magister/homework/add_label") throw wsError(code);
      return { appointments: APPOINTMENTS };
    });
    await choose(card, inner);
    field<HTMLFormElement>(inner, "form").dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(inner.querySelector('.error[role="alert"]')?.textContent).toBe(message);
    expect(root(card).querySelector("magister-label-dialog")).not.toBeNull();
    expect(save(inner).disabled).toBe(false);
  });

  it("closes on Escape, the close button and Cancel, giving focus back", async () => {
    for (const how of ["escape", "close", "cancel"]) {
      document.body.innerHTML = "";
      const { card, inner } = await open();
      if (how === "escape") {
        const event = new Event("cancel", { cancelable: true });
        field<HTMLDialogElement>(inner, "dialog").dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
      } else {
        field<HTMLButtonElement>(inner, how === "close" ? ".close" : ".secondary").click();
      }
      await flush(card);
      expect(root(card).querySelector("magister-label-dialog")).toBeNull();
      expect(root(card).activeElement).toBe(root(card).querySelector(".add"));
    }
  });

  it("does not save twice while a save is running", async () => {
    let resolve: (value: unknown) => void = () => undefined;
    const { card, callWS, inner } = await open((message) =>
      message["type"] === "magister/homework/add_label"
        ? new Promise((r) => (resolve = r))
        : { appointments: APPOINTMENTS },
    );
    await choose(card, inner);
    const form = field<HTMLFormElement>(inner, "form");
    form.dispatchEvent(new Event("submit", { cancelable: true }));
    form.dispatchEvent(new Event("submit", { cancelable: true }));
    await flush(card);
    expect(callWS.mock.calls.filter((c) => c[0].type === "magister/homework/add_label")).toHaveLength(1);
    expect(save(inner).disabled).toBe(true);
    expect(save(inner).textContent.trim()).toBe("Saving…");
    resolve({});
    await flush(card);
  });
});


describe("Dutch label texts", () => {
  it("uses the exact accessible name for the remove button", async () => {
    const { card, connection } = await mount({}, vi.fn(), "nl");
    connection.push(payload([item({ manual_labels: [manual()] })], { labels: LABELS }));
    await flush(card);
    expect(button(card, ".chip-remove").getAttribute("aria-label")).toBe("Label verwijderen");
  });
});
