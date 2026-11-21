import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../src/index";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { MagisterTimerCard } from "../src/timer-card";
import {
  availability,
  currentSettings,
  momentId,
  notifyState,
  playTone,
  resetNotificationsForTests,
  setEnabled,
  setSound,
} from "../src/notifications";
import { TRANSLATIONS } from "../src/translations";
import type { StudyTimer, TimerSettings } from "../src/types";
import { FakeConnection, makeHass, ENTITY } from "./helpers";
import { NO_EXTRA, parent, sub, timer, timerPayload } from "./timer-fixtures";

const SETTINGS_KEY = "magister.notifications";

// -- mocks --

class FakeNotification {
  static instances: FakeNotification[] = [];
  static permission: NotificationPermission = "granted";
  static next: NotificationPermission = "granted";
  static requestPermission = vi.fn(() => {
    FakeNotification.permission = FakeNotification.next;
    return Promise.resolve(FakeNotification.permission);
  });
  onclick: (() => void) | null = null;
  close = vi.fn();
  constructor(
    readonly title: string,
    readonly options: NotificationOptions = {},
  ) {
    FakeNotification.instances.push(this);
  }
}

class FakeChannel {
  static instances: FakeChannel[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  constructor(readonly name: string) {
    FakeChannel.instances.push(this);
  }
  postMessage(data: unknown): void {
    for (const other of FakeChannel.instances) {
      if (other !== this && other.name === this.name) other.onmessage?.({ data } as MessageEvent);
    }
  }
  close(): void {
    FakeChannel.instances = FakeChannel.instances.filter((channel) => channel !== this);
  }
}

class FakeAudio {
  static instances: FakeAudio[] = [];
  static started = 0;
  state = "running";
  currentTime = 0;
  destination = {};
  resume = vi.fn(() => Promise.resolve());
  constructor() {
    FakeAudio.instances.push(this);
  }
  createOscillator() {
    return {
      type: "",
      frequency: { value: 0 },
      connect: vi.fn(),
      start: vi.fn(() => {
        FakeAudio.started++;
      }),
      stop: vi.fn(),
    };
  }
  createGain() {
    return {
      gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
      connect: vi.fn(),
    };
  }
}

const define = (target: object, key: string, value: unknown): void => {
  Object.defineProperty(target, key, { value, configurable: true, writable: true });
};

const USER_AGENT = navigator.userAgent;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
  vi.setSystemTime(new Date("2026-11-13T09:30:00Z"));
  FakeNotification.instances = [];
  FakeNotification.permission = "granted";
  FakeNotification.next = "granted";
  FakeNotification.requestPermission.mockClear();
  FakeChannel.instances = [];
  FakeAudio.instances = [];
  FakeAudio.started = 0;
  define(globalThis, "Notification", FakeNotification);
  define(globalThis, "BroadcastChannel", FakeChannel);
  define(globalThis, "AudioContext", FakeAudio);
  define(globalThis, "isSecureContext", true);
  define(globalThis.navigator, "userAgent", USER_AGENT);
  window.localStorage.clear();
  resetNotificationsForTests();
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.useRealTimers();
  resetNotificationsForTests();
});

const turnOn = (sound = true): void => {
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify({ enabled: true, sound }));
};

// -- cards --

async function flush(card: MagisterTimerCard | MagisterHomeworkCard): Promise<void> {
  for (let round = 0; round < 4; round++) {
    await Promise.resolve();
    await card.updateComplete;
  }
}

interface Mounted {
  card: MagisterTimerCard;
  connection: FakeConnection;
}

async function mountTimer(
  studyTimer: StudyTimer | null,
  settings: TimerSettings = { prewarn_minutes: 5, extra_minutes: 5 },
  language = "en",
): Promise<Mounted> {
  const connection = new FakeConnection();
  const card = document.createElement("magister-timer-card") as MagisterTimerCard;
  card.setConfig({ type: "custom:magister-timer-card", entity: ENTITY });
  card.hass = makeHass(connection, vi.fn(), language);
  document.body.append(card);
  await flush(card);
  connection.push(timerPayload([parent([sub("a"), sub("b")])], { timer: studyTimer, settings }));
  await flush(card);
  return { card, connection };
}

async function advance(cards: MagisterTimerCard[], ms: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms);
  for (const card of cards) await flush(card);
}

const shown = (): string[] => FakeNotification.instances.map((instance) => instance.title);

describe("when a notification is shown", () => {
  it("shows the pre-warning and the end once each, with a tag per child and the sound", async () => {
    turnOn();
    const { card } = await mountTimer(timer());
    await advance([card], 1_500_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
    expect(FakeNotification.instances[0]?.options.tag).toBe(`magister-timer-${ENTITY}`);
    expect(FakeAudio.started).toBe(2);
    await advance([card], 60_000);
    expect(shown()).toHaveLength(1);
    await advance([card], 240_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)", "Time is up: Stap a (Engels)"]);
    await advance([card], 600_000);
    expect(shown()).toHaveLength(2);
  });

  it("shows one notification with two cards on the page", async () => {
    turnOn();
    const first = await mountTimer(timer());
    const second = await mountTimer(timer());
    await advance([first.card, second.card], 1_500_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
    await advance([first.card, second.card], 300_000);
    expect(shown()).toHaveLength(2);
    expect(FakeAudio.started).toBe(4);
  });

  it("does not show a moment another tab has claimed (localStorage)", async () => {
    turnOn();
    const key = `magister.notify.claim.${momentId({
      child: ENTITY,
      startedAt: timer().started_at,
      endsAt: timer().ends_at,
      moment: "prewarn",
    })}`;
    window.localStorage.setItem(key, `other|${String(Date.now())}`);
    const { card } = await mountTimer(timer());
    await advance([card], 1_500_000);
    expect(shown()).toEqual([]);
    await advance([card], 300_000);
    expect(shown()).toEqual(["Time is up: Stap a (Engels)"]);
  });

  it("does not show a moment another tab announced on the channel when localStorage fails", async () => {
    turnOn();
    const { card } = await mountTimer(timer());
    const other = new FakeChannel("magister-notifications");
    other.postMessage({
      claim: momentId({ child: ENTITY, startedAt: timer().started_at, endsAt: timer().ends_at, moment: "prewarn" }),
    });
    await advance([card], 1_500_000);
    expect(shown()).toEqual([]);
  });

  it("does not notify for moments that passed before the card opened", async () => {
    turnOn();
    vi.setSystemTime(new Date("2026-11-13T09:57:00Z"));
    const early = await mountTimer(timer());
    await advance([early.card], 60_000);
    expect(shown()).toEqual([]);
    document.body.innerHTML = "";
    vi.setSystemTime(new Date("2026-11-13T10:30:00Z"));
    const late = await mountTimer(timer());
    await advance([late.card], 10_000);
    expect(shown()).toEqual([]);
  });

  it("notifies the new end once after an extension", async () => {
    turnOn();
    const { card, connection } = await mountTimer(timer());
    await advance([card], 1_800_000);
    expect(shown()).toHaveLength(2);
    // the extension: running again for 5 minutes, same started_at
    connection.push(
      timerPayload([parent([sub("a"), sub("b")])], {
        timer: timer({ minutes: 5, ends_at: "2026-11-13T10:05:00+00:00" }),
        settings: { prewarn_minutes: 5, extra_minutes: 5 },
      }),
    );
    await flush(card);
    await advance([card], 300_000);
    expect(shown()).toEqual([
      "5 minutes left: Stap a (Engels)",
      "Time is up: Stap a (Engels)",
      "Time is up: Stap a (Engels)",
    ]);
    await advance([card], 300_000);
    expect(shown()).toHaveLength(3);
  });

  it("shows nothing while the browser setting is off", async () => {
    const { card } = await mountTimer(timer());
    await advance([card], 1_800_000);
    expect(shown()).toEqual([]);
    expect(FakeAudio.started).toBe(0);
  });

  it("shows nothing when the permission is denied or default", async () => {
    turnOn();
    FakeNotification.permission = "denied";
    const denied = await mountTimer(timer());
    await advance([denied.card], 1_800_000);
    expect(shown()).toEqual([]);
    FakeNotification.permission = "default";
    expect(notifyState().active).toBe(false);
  });

  it("plays no sound when the sound is off, and skips it silently when blocked", async () => {
    turnOn(false);
    const quiet = await mountTimer(timer());
    await advance([quiet.card], 1_500_000);
    expect(shown()).toHaveLength(1);
    expect(FakeAudio.started).toBe(0);

    document.body.innerHTML = "";
    window.localStorage.clear();
    resetNotificationsForTests();
    turnOn(true);
    define(globalThis, "AudioContext", function blocked() {
      throw new Error("blocked");
    });
    const blocked = await mountTimer(timer({ started_at: "2026-11-13T09:31:00+00:00" }));
    await advance([blocked.card], 1_500_000);
    expect(shown()).toHaveLength(2);
    expect(() => {
      playTone();
    }).not.toThrow();
  });

  it("omits the subject when there is none, and uses the singular", async () => {
    turnOn();
    const { card } = await mountTimer(timer({ subject: "", minutes: 3 }), { prewarn_minutes: 1, extra_minutes: null });
    await advance([card], 1_739_000);
    expect(shown()).toEqual([]);
    await advance([card], 2_000);
    expect(shown()).toEqual(["1 minute left: Stap a"]);
  });
});

describe("texts", () => {
  it("speaks Dutch", async () => {
    turnOn();
    const { card } = await mountTimer(timer(), { prewarn_minutes: 5, extra_minutes: null }, "nl");
    await advance([card], 1_500_000);
    await advance([card], 300_000);
    expect(shown()).toEqual(["Nog 5 minuten: Stap a (Engels)", "Tijd is om: Stap a (Engels)"]);
  });

  it("has the same notification texts in both languages", () => {
    expect(TRANSLATIONS.nl.timer.notify_prewarn_one).toBe("Nog 1 minuut: {what}");
    expect(TRANSLATIONS.en.timer.notify_end).toBe("Time is up: {what}");
  });

  it("uses Dutch for the singular", async () => {
    turnOn();
    const { card } = await mountTimer(timer({ minutes: 3 }), { prewarn_minutes: 1, extra_minutes: null }, "nl");
    await advance([card], 1_741_000);
    expect(shown()).toEqual(["Nog 1 minuut: Stap a (Engels)"]);
  });
});

describe("click", () => {
  it("focuses the window and closes the notification", async () => {
    turnOn();
    const focus = vi.spyOn(window, "focus").mockImplementation(() => undefined);
    const { card } = await mountTimer(timer());
    await advance([card], 1_500_000);
    const notification = FakeNotification.instances[0];
    expect(notification?.options).not.toHaveProperty("actions");
    notification?.onclick?.();
    expect(focus).toHaveBeenCalled();
    expect(notification?.close).toHaveBeenCalled();
  });
});

describe("permission states", () => {
  it("reports unsupported, insecure and the HA app", () => {
    expect(availability()).toBe("ok");
    define(globalThis, "isSecureContext", false);
    expect(availability()).toBe("insecure");
    define(globalThis, "isSecureContext", true);
    define(globalThis, "Notification", undefined);
    expect(availability()).toBe("unsupported");
    define(globalThis, "Notification", FakeNotification);
    define(globalThis.navigator, "userAgent", "Mozilla/5.0 Home Assistant/2026.11 (Android)");
    expect(availability()).toBe("app");
    expect(notifyState().active).toBe(false);
  });

  it("asks for permission when switching on and stores the choice", async () => {
    FakeNotification.permission = "default";
    await setEnabled(true);
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);
    expect(currentSettings()).toEqual({ enabled: true, sound: true });
    expect(JSON.parse(window.localStorage.getItem(SETTINGS_KEY) ?? "{}")).toEqual({ enabled: true, sound: true });
  });

  it("stays off when the browser denies", async () => {
    FakeNotification.permission = "default";
    FakeNotification.next = "denied";
    await setEnabled(true);
    expect(currentSettings().enabled).toBe(false);
  });

  it("does not switch on when denied, unsupported, insecure or in the app", async () => {
    FakeNotification.permission = "denied";
    await setEnabled(true);
    expect(currentSettings().enabled).toBe(false);
    FakeNotification.permission = "granted";
    define(globalThis, "isSecureContext", false);
    await setEnabled(true);
    expect(currentSettings().enabled).toBe(false);
    expect(FakeNotification.requestPermission).not.toHaveBeenCalled();
  });

  it("switches off and keeps the sound choice", async () => {
    await setEnabled(true);
    setSound(false);
    await setEnabled(false);
    expect(currentSettings()).toEqual({ enabled: false, sound: false });
  });

  it("tolerates a failing localStorage", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(currentSettings()).toEqual({ enabled: false, sound: true });
    await setEnabled(true);
    expect(currentSettings().enabled).toBe(true);
    const { card } = await mountTimer(timer());
    await advance([card], 1_500_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
  });

  it("ignores broken stored settings", () => {
    window.localStorage.setItem(SETTINGS_KEY, "{not json");
    expect(currentSettings()).toEqual({ enabled: false, sound: true });
  });
});

describe("the settings in the cards", () => {
  const root = (card: MagisterTimerCard): ShadowRoot => {
    if (!card.shadowRoot) throw new Error("no shadow root");
    return card.shadowRoot;
  };
  const input = (card: MagisterTimerCard, id: string): HTMLInputElement | null =>
    root(card).querySelector<HTMLInputElement>(`#${id}`);

  async function openPanel(card: MagisterTimerCard): Promise<void> {
    root(card).querySelector<HTMLButtonElement>("[data-notify-button]")?.click();
    await flush(card);
  }

  it("switches on from the timer card, asks permission, and then offers the sound", async () => {
    FakeNotification.permission = "default";
    const { card } = await mountTimer(timer());
    await openPanel(card);
    expect(input(card, "timer-notify-sound")).toBeNull();
    const box = input(card, "timer-notify");
    if (!box) throw new Error("no checkbox");
    box.checked = true;
    box.dispatchEvent(new Event("change"));
    await flush(card);
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);
    expect(input(card, "timer-notify")?.checked).toBe(true);
    const sound = input(card, "timer-notify-sound");
    expect(sound?.checked).toBe(true);
    if (!sound) throw new Error("no sound checkbox");
    sound.checked = false;
    sound.dispatchEvent(new Event("change"));
    await flush(card);
    expect(currentSettings()).toEqual({ enabled: true, sound: false });
  });

  it("explains a denied permission", async () => {
    FakeNotification.permission = "denied";
    const { card } = await mountTimer(timer());
    await openPanel(card);
    expect(root(card).querySelector(".notify-denied")?.textContent).toBe("Your browser does not allow notifications");
    expect(input(card, "timer-notify")?.checked).toBe(false);
  });

  it("hides the option with an explanation when unsupported, insecure or in the app", async () => {
    define(globalThis, "isSecureContext", false);
    const insecure = await mountTimer(timer());
    await openPanel(insecure.card);
    expect(input(insecure.card, "timer-notify")).toBeNull();
    expect(root(insecure.card).querySelector(".notify-unavailable")?.textContent).toContain("https");

    document.body.innerHTML = "";
    define(globalThis, "isSecureContext", true);
    define(globalThis, "Notification", undefined);
    const unsupported = await mountTimer(timer());
    await openPanel(unsupported.card);
    expect(root(unsupported.card).querySelector(".notify-unavailable")?.textContent).toContain("does not support");

    document.body.innerHTML = "";
    define(globalThis, "Notification", FakeNotification);
    define(globalThis.navigator, "userAgent", "Home Assistant/2026.11");
    const app = await mountTimer(timer(), NO_EXTRA, "nl");
    await openPanel(app.card);
    expect(input(app.card, "timer-notify")).toBeNull();
    expect(root(app.card).querySelector(".notify-unavailable")?.textContent).toBe("Gebruik de meldingen van de app.");
  });

  it("is in the settings panel of the homework card and follows changes of another card", async () => {
    turnOn();
    const connection = new FakeConnection();
    const card = document.createElement("magister-homework-card") as MagisterHomeworkCard;
    card.setConfig({ type: "custom:magister-homework-card", entity: ENTITY });
    card.hass = makeHass(connection, vi.fn(), "nl");
    document.body.append(card);
    await flush(card);
    connection.push(timerPayload([parent([sub("a")])], { timer: null }));
    await flush(card);
    card.shadowRoot?.querySelector<HTMLButtonElement>("[data-timer-settings-button]")?.click();
    await flush(card);
    const labels = card.shadowRoot?.querySelector(".timer-notify")?.textContent ?? "";
    expect(labels).toContain("Meldingen in deze browser");
    expect(labels).toContain("Geluid");
    expect(card.shadowRoot?.querySelector<HTMLInputElement>("#timer-notify")?.checked).toBe(true);
    setSound(false);
    await flush(card);
    expect(card.shadowRoot?.querySelector<HTMLInputElement>("#timer-notify-sound")?.checked).toBe(false);
    await setEnabled(false);
    await flush(card);
    expect(card.shadowRoot?.querySelector("#timer-notify-sound")).toBeNull();
  });
});
