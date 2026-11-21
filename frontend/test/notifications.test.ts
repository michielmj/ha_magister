import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "../src/index";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { MagisterTimerCard } from "../src/timer-card";
import {
  availability,
  claim,
  currentSettings,
  listen,
  momentId,
  notifyMoment,
  notifyState,
  onChange,
  playTone,
  resetNotificationsForTests,
  setEnabled,
  setSound,
  unlockAudio,
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
  /** The constructor throws (Chrome on Android). */
  static throwing = false;
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
    if (FakeNotification.throwing) throw new TypeError("Illegal constructor");
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
  static initial = "running";
  state = FakeAudio.initial;
  currentTime = 0;
  destination = {};
  resume = vi.fn(() => {
    this.state = "running";
    return Promise.resolve();
  });
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
  FakeNotification.throwing = false;
  FakeNotification.requestPermission.mockClear();
  FakeChannel.instances = [];
  FakeAudio.instances = [];
  FakeAudio.started = 0;
  FakeAudio.initial = "running";
  define(globalThis.navigator, "locks", undefined);
  define(globalThis.navigator, "permissions", undefined);
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
  callWS: unknown = vi.fn(),
): Promise<Mounted> {
  const connection = new FakeConnection();
  const card = document.createElement("magister-timer-card") as MagisterTimerCard;
  card.setConfig({ type: "custom:magister-timer-card", entity: ENTITY });
  card.hass = makeHass(connection, callWS, language);
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

/** The notifications of the moments (not the silent probe of switching on). */
const real = (): FakeNotification[] =>
  FakeNotification.instances.filter((instance) => instance.options.tag !== "magister-test");
const shown = (): string[] => real().map((instance) => instance.title);

describe("when a notification is shown", () => {
  it("shows the pre-warning and the end once each, with a tag per child and the sound", async () => {
    turnOn();
    const { card } = await mountTimer(timer());
    await advance([card], 1_500_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
    expect(real()[0]?.options.tag).toBe(`magister-timer-${ENTITY}`);
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
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    await setEnabled(true);
    expect(currentSettings().enabled).toBe(true);
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
    const notification = real()[0];
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

// -- the 1.10.1 fix round --

interface Inside {
  _timer: {
    announcement: string;
    _stopTicker: () => void;
    openSettings(): void;
    patchSettings(patch: { prewarn?: string; extra?: string }): void;
    saveSettings(): Promise<void>;
  };
}
const inside = (card: MagisterTimerCard): Inside["_timer"] => (card as unknown as Inside)._timer;

describe("the notification options", () => {
  it("renotifies, and sets the tag per child and the language", async () => {
    turnOn();
    const { card } = await mountTimer(timer(), { prewarn_minutes: 5, extra_minutes: null }, "nl");
    await advance([card], 1_800_000);
    expect(real()).toHaveLength(2);
    for (const notification of real()) {
      expect(notification.options).toMatchObject({
        tag: `magister-timer-${ENTITY}`,
        lang: "nl",
        renotify: true,
      });
    }
  });
});

/** Change the pre-warning setting the way the panel does: open, choose, save. */
async function save(card: MagisterTimerCard, prewarn: string): Promise<void> {
  const controller = inside(card);
  controller.openSettings();
  controller.patchSettings({ prewarn });
  await controller.saveSettings();
  await flush(card);
}

describe("a pre-warning that was already sent", () => {
  it("is not announced or notified when the timer is first seen with prewarned", async () => {
    turnOn();
    const { card } = await mountTimer(timer({ prewarned: true }));
    await advance([card], 1_500_000);
    expect(shown()).toEqual([]);
    expect(inside(card).announcement).toBe("");
    await advance([card], 300_000);
    expect(shown()).toEqual(["Time is up: Stap a (Engels)"]);
  });

  it("still notifies when prewarned is false or absent", async () => {
    turnOn();
    const { card } = await mountTimer(timer({ prewarned: false }));
    await advance([card], 1_500_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
    expect(inside(card).announcement).not.toBe("");
  });

  it("does not show it twice when the push that flips prewarned follows the moment", async () => {
    turnOn();
    const { card, connection } = await mountTimer(timer());
    await advance([card], 1_500_000);
    connection.push(
      timerPayload([parent([sub("a"), sub("b")])], {
        timer: timer({ prewarned: true }),
        settings: { prewarn_minutes: 5, extra_minutes: 5 },
      }),
    );
    await flush(card);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
  });
});

describe("a pre-warning push just before the local crossing", () => {
  it("does not cancel the armed pre-warning", async () => {
    turnOn();
    const { card, connection } = await mountTimer(timer());
    inside(card)._stopTicker();
    await advance([card], 1_499_000);
    expect(shown()).toEqual([]);
    connection.push(
      timerPayload([parent([sub("a"), sub("b")])], {
        timer: timer({ prewarned: true }),
        settings: { prewarn_minutes: 5, extra_minutes: 5 },
      }),
    );
    await flush(card);
    inside(card)._stopTicker();
    await advance([card], 2_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
    await advance([card], 60_000);
    expect(shown()).toHaveLength(1);
  });
});

describe("the pre-warning switched on while the timer runs", () => {
  const callWS = (): ReturnType<typeof vi.fn> =>
    vi.fn().mockResolvedValue({ timer_settings: { prewarn_minutes: 5, extra_minutes: null } });

  it("is announced and notified once its moment is reached", async () => {
    turnOn();
    const { card } = await mountTimer(timer(), { prewarn_minutes: null, extra_minutes: null }, "en", callWS());
    await advance([card], 60_000);
    await save(card, "5");
    await advance([card], 1_400_000);
    expect(shown()).toEqual([]);
    await advance([card], 45_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
    expect(inside(card).announcement).not.toBe("");
    await advance([card], 60_000);
    expect(shown()).toHaveLength(1);
  });

  it("is not announced when its moment was already past when it was switched on", async () => {
    turnOn();
    const { card } = await mountTimer(timer(), { prewarn_minutes: null, extra_minutes: null }, "en", callWS());
    await advance([card], 1_560_000);
    await save(card, "5");
    await advance([card], 30_000);
    expect(shown()).toEqual([]);
    expect(inside(card).announcement).toBe("");
    await advance([card], 300_000);
    expect(shown()).toEqual(["Time is up: Stap a (Engels)"]);
  });
});

describe("one-shot timers for the moments", () => {
  it("are armed, fire observe in a tab whose ticker is throttled, and are cleared on disconnect", async () => {
    turnOn();
    const { card } = await mountTimer(timer());
    const controller = inside(card);
    // the ticker, the pre-warning and the end
    expect(vi.getTimerCount()).toBe(3);
    controller._stopTicker(); // what a hidden tab does to it
    await advance([card], 1_500_049);
    expect(shown()).toEqual([]);
    await advance([card], 1);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)"]);
    await advance([card], 300_000);
    expect(shown()).toEqual(["5 minutes left: Stap a (Engels)", "Time is up: Stap a (Engels)"]);
    card.remove();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("are cleared on disconnect before they fire", async () => {
    const { card } = await mountTimer(timer());
    expect(vi.getTimerCount()).toBe(3);
    card.remove();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("are re-armed when the payload changes", async () => {
    const { card, connection } = await mountTimer(timer());
    const spy = vi.spyOn(globalThis, "setTimeout");
    connection.push(
      timerPayload([parent([sub("a"), sub("b")])], {
        timer: timer({ minutes: 60, ends_at: "2026-11-13T10:30:00+00:00" }),
        settings: { prewarn_minutes: 5, extra_minutes: 5 },
      }),
    );
    await flush(card);
    const delays = spy.mock.calls.map((call) => call[1]);
    expect(delays).toContain(3_300_050);
    expect(delays).toContain(3_600_050);
    // no stale timers: the ticker and the two new ones
    expect(vi.getTimerCount()).toBe(3);
    // and none when the timer is paused
    connection.push(
      timerPayload([parent([sub("a"), sub("b")])], {
        timer: { ...timer(), state: "paused", remaining: 600 },
        settings: { prewarn_minutes: 5, extra_minutes: 5 },
      }),
    );
    await flush(card);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("are re-armed when the tab becomes visible again", async () => {
    const { card } = await mountTimer(timer());
    await advance([card], 120_000);
    const spy = vi.spyOn(globalThis, "setTimeout");
    document.dispatchEvent(new Event("visibilitychange"));
    await flush(card);
    const delays = spy.mock.calls.map((call) => call[1]);
    expect(delays).toContain(1_380_050);
    expect(delays).toContain(1_680_050);
    expect(vi.getTimerCount()).toBe(3);
    card.remove();
    spy.mockClear();
    document.dispatchEvent(new Event("visibilitychange"));
    expect(spy).not.toHaveBeenCalled();
  });

  it("are re-armed after a settings save, through saveSettings", async () => {
    const callWS = vi.fn().mockResolvedValue({ timer_settings: { prewarn_minutes: 5, extra_minutes: null } });
    const { card } = await mountTimer(timer(), { prewarn_minutes: null, extra_minutes: null }, "en", callWS);
    // the ticker and the end
    expect(vi.getTimerCount()).toBe(2);
    await save(card, "5");
    expect(callWS).toHaveBeenCalledWith({
      type: "magister/homework/timer_settings",
      entity_id: ENTITY,
      prewarn_minutes: 5,
      extra_minutes: null,
    });
    // the ticker, the pre-warning and the end
    expect(vi.getTimerCount()).toBe(3);
  });

  it("are not created from the tick", async () => {
    const { card } = await mountTimer(timer());
    const spy = vi.spyOn(globalThis, "setTimeout");
    await advance([card], 10_000);
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("the claim with a Web Lock", () => {
  const install = (held = new Set<string>()) => {
    const request = vi.fn(async (name: string, _options: unknown, callback: (lock: unknown) => Promise<void>) => {
      if (held.has(name)) {
        await callback(null);
        return;
      }
      held.add(name);
      try {
        await callback({ name });
      } finally {
        held.delete(name);
      }
    });
    define(globalThis.navigator, "locks", { request });
    return { request, held };
  };
  const info = {
    child: ENTITY,
    startedAt: "2026-11-13T09:30:00+00:00",
    endsAt: "2026-11-13T10:00:00+00:00",
    moment: "end" as const,
    text: "Time is up",
    language: "en",
  };

  it("lets two simultaneous claims show one notification", async () => {
    turnOn();
    const { request } = install();
    notifyMoment(info);
    notifyMoment(info);
    await vi.advanceTimersByTimeAsync(0);
    expect(request).toHaveBeenCalledTimes(2);
    expect(request.mock.calls[0]?.[0]).toBe(`magister.notify.claim.${momentId(info)}`);
    expect(request.mock.calls[0]?.[1]).toEqual({ ifAvailable: true });
    expect(shown()).toEqual(["Time is up"]);
  });

  it("shows nothing when another tab holds the lock", async () => {
    turnOn();
    install(new Set([`magister.notify.claim.${momentId(info)}`]));
    notifyMoment(info);
    await vi.advanceTimersByTimeAsync(0);
    expect(shown()).toEqual([]);
  });

  it("holds the lock for two minutes after showing", async () => {
    turnOn();
    const { held } = install();
    notifyMoment(info);
    await vi.advanceTimersByTimeAsync(1000);
    expect(held.size).toBe(1);
    await vi.advanceTimersByTimeAsync(120_000);
    expect(held.size).toBe(0);
  });

  it("falls back to the claim without navigator.locks", () => {
    turnOn();
    define(globalThis.navigator, "locks", undefined);
    notifyMoment(info);
    notifyMoment(info);
    expect(shown()).toEqual(["Time is up"]);
  });

  it("keeps the localStorage claim with a lock", async () => {
    turnOn();
    install();
    notifyMoment(info);
    await vi.advanceTimersByTimeAsync(0);
    expect(window.localStorage.getItem(`magister.notify.claim.${momentId(info)}`)).not.toBeNull();
  });
});

describe("a constructor that throws", () => {
  it("is probed once when switching on, with a silent test notification", async () => {
    await setEnabled(true, "Notifications are on");
    expect(FakeNotification.instances).toHaveLength(1);
    const probe = FakeNotification.instances[0];
    expect(probe?.title).toBe("Notifications are on");
    expect(probe?.options).toMatchObject({ tag: "magister-test", silent: true });
    expect(probe?.close).toHaveBeenCalled();
    expect(currentSettings().enabled).toBe(true);
  });

  it("switches off, is remembered and is shown as unsupported", async () => {
    FakeNotification.throwing = true;
    await setEnabled(true);
    expect(currentSettings().enabled).toBe(false);
    expect(window.localStorage.getItem("magister.notifications.constructorBroken")).toBe("1");
    expect(availability()).toBe("unsupported");
    // a new page load knows it too
    resetNotificationsForTests();
    expect(availability()).toBe("unsupported");
    const { card } = await mountTimer(timer());
    card.shadowRoot?.querySelector<HTMLButtonElement>("[data-notify-button]")?.click();
    await flush(card);
    expect(card.shadowRoot?.querySelector("#timer-notify")).toBeNull();
    expect(card.shadowRoot?.querySelector(".notify-unavailable")?.textContent).toContain("does not support");
  });

  it("shows the unsupported panel right after the checkbox is used", async () => {
    FakeNotification.throwing = true;
    const { card } = await mountTimer(timer());
    card.shadowRoot?.querySelector<HTMLButtonElement>("[data-notify-button]")?.click();
    await flush(card);
    const box = card.shadowRoot?.querySelector<HTMLInputElement>("#timer-notify");
    if (!box) throw new Error("no checkbox");
    box.checked = true;
    box.dispatchEvent(new Event("change"));
    await flush(card);
    expect(card.shadowRoot?.querySelector("#timer-notify")).toBeNull();
    expect(card.shadowRoot?.querySelector(".notify-unavailable")).not.toBeNull();
  });

  it("still plays the tone when a moment cannot be shown", async () => {
    turnOn();
    FakeNotification.throwing = true;
    const { card } = await mountTimer(timer());
    await advance([card], 1_500_000);
    expect(FakeNotification.instances).toHaveLength(0);
    expect(FakeAudio.started).toBe(2);
  });
});

describe("unlocking the sound after a reload", () => {
  it("unlocks on the first click when notifications are active and sound is on, then stops listening", async () => {
    turnOn();
    FakeAudio.initial = "suspended";
    window.dispatchEvent(new Event("pointerdown"));
    const context = FakeAudio.instances[0];
    expect(context?.resume).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    await Promise.resolve();
    window.dispatchEvent(new Event("pointerdown"));
    window.dispatchEvent(new Event("keydown"));
    expect(context?.resume).toHaveBeenCalledTimes(1);
    expect(FakeAudio.instances).toHaveLength(1);
  });

  it.each(["pointerup", "touchend", "click"])("also unlocks on %s, in the capture phase", async (type) => {
    turnOn();
    FakeAudio.initial = "suspended";
    const remove = vi.spyOn(window, "removeEventListener");
    document.body.dispatchEvent(new Event(type, { bubbles: false }));
    expect(FakeAudio.instances[0]?.resume).toHaveBeenCalledTimes(1);
    await Promise.resolve();
    await Promise.resolve();
    const removed = remove.mock.calls.filter((call) => call[2] === true).map((call) => call[0]);
    expect(removed.sort()).toEqual(["click", "keydown", "pointerdown", "pointerup", "touchend"]);
    for (const other of ["pointerdown", "pointerup", "touchend", "click", "keydown"]) {
      window.dispatchEvent(new Event(other));
    }
    expect(FakeAudio.instances[0]?.resume).toHaveBeenCalledTimes(1);
  });

  it("also unlocks on a key press", () => {
    turnOn();
    FakeAudio.initial = "suspended";
    window.dispatchEvent(new Event("keydown"));
    expect(FakeAudio.instances[0]?.resume).toHaveBeenCalledTimes(1);
  });

  it("does nothing while notifications are off or the sound is off", () => {
    FakeAudio.initial = "suspended";
    window.dispatchEvent(new Event("pointerdown"));
    turnOn(false);
    window.dispatchEvent(new Event("pointerdown"));
    expect(FakeAudio.instances).toHaveLength(0);
  });

  it("exports unlockAudio, which resumes a suspended context", () => {
    FakeAudio.initial = "suspended";
    unlockAudio();
    expect(FakeAudio.instances[0]?.resume).toHaveBeenCalledTimes(1);
  });
});

describe("the cards and the storage", () => {
  const root = (card: MagisterTimerCard): ShadowRoot => {
    if (!card.shadowRoot) throw new Error("no shadow root");
    return card.shadowRoot;
  };

  async function openPanel(card: MagisterTimerCard): Promise<void> {
    root(card).querySelector<HTMLButtonElement>("[data-notify-button]")?.click();
    await flush(card);
  }

  it("asks for permission synchronously in the change handler, before anything is flushed", async () => {
    FakeNotification.permission = "default";
    const { card } = await mountTimer(timer());
    await openPanel(card);
    const box = root(card).querySelector<HTMLInputElement>("#timer-notify");
    if (!box) throw new Error("no checkbox");
    box.checked = true;
    box.dispatchEvent(new Event("change"));
    expect(FakeNotification.requestPermission).toHaveBeenCalledTimes(1);
  });

  it("re-renders on a storage event of another tab", async () => {
    const { card } = await mountTimer(timer());
    await openPanel(card);
    expect(root(card).querySelector<HTMLInputElement>("#timer-notify")?.checked).toBe(false);
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify({ enabled: true, sound: true }));
    window.dispatchEvent(new StorageEvent("storage", { key: SETTINGS_KEY }));
    await flush(card);
    expect(root(card).querySelector<HTMLInputElement>("#timer-notify")?.checked).toBe(true);
    expect(root(card).querySelector("#timer-notify-sound")).not.toBeNull();
  });

  it("unsubscribes when disconnected, so the listeners do not grow", async () => {
    const { card } = await mountTimer(timer());
    const update = vi.spyOn(card, "requestUpdate");
    card.remove();
    for (let round = 0; round < 3; round++) {
      document.body.append(card);
      await flush(card);
      card.remove();
    }
    update.mockClear();
    setSound(false);
    expect(update).not.toHaveBeenCalled();
    document.body.append(card);
    await flush(card);
    update.mockClear();
    setSound(true);
    expect(update).toHaveBeenCalledTimes(1);
  });

  it("onChange hands out an unsubscribe", () => {
    const listener = vi.fn();
    const off = onChange(listener);
    setSound(false);
    off();
    setSound(true);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("prunes claims older than 24 hours when a new moment is claimed", () => {
    const now = Date.now();
    window.localStorage.setItem("magister.notify.claim.old", `x|${String(now - 25 * 3600_000)}`);
    window.localStorage.setItem("magister.notify.claim.fresh", `x|${String(now - 3600_000)}`);
    window.localStorage.setItem("magister.notify.claim.junk", "x|nonsense");
    window.localStorage.setItem("other.key", "x|1");
    expect(claim("a|b|end|c")).toBe(true);
    expect(window.localStorage.getItem("magister.notify.claim.old")).toBeNull();
    expect(window.localStorage.getItem("magister.notify.claim.junk")).toBeNull();
    expect(window.localStorage.getItem("magister.notify.claim.fresh")).not.toBeNull();
    expect(window.localStorage.getItem("other.key")).not.toBeNull();
    expect(window.localStorage.getItem("magister.notify.claim.a|b|end|c")).not.toBeNull();
  });

  it("uses the in-memory choice only when the write failed, not when the key is missing", async () => {
    await setEnabled(true);
    expect(currentSettings().enabled).toBe(true);
    window.localStorage.removeItem(SETTINGS_KEY);
    expect(currentSettings()).toEqual({ enabled: false, sound: true });
  });

  it("re-emits when the browser permission changes", async () => {
    const status: { onchange: (() => void) | null } = { onchange: null };
    define(globalThis.navigator, "permissions", { query: vi.fn(() => Promise.resolve(status)) });
    const listener = vi.fn();
    onChange(listener);
    listen();
    await Promise.resolve();
    await Promise.resolve();
    status.onchange?.();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("keeps the notification checkbox out of the settings form", async () => {
    const connection = new FakeConnection();
    const card = document.createElement("magister-homework-card") as MagisterHomeworkCard;
    card.setConfig({ type: "custom:magister-homework-card", entity: ENTITY });
    card.hass = makeHass(connection, vi.fn(), "en");
    document.body.append(card);
    await flush(card);
    connection.push(timerPayload([parent([sub("a")])], { timer: null }));
    await flush(card);
    card.shadowRoot?.querySelector<HTMLButtonElement>("[data-timer-settings-button]")?.click();
    await flush(card);
    expect(card.shadowRoot?.querySelector("form.timer-settings")).not.toBeNull();
    expect(card.shadowRoot?.querySelector("#timer-notify")).not.toBeNull();
    expect(card.shadowRoot?.querySelector("form #timer-notify")).toBeNull();
    // Escape in the notification part closes the settings, like in the form
    card.shadowRoot
      ?.querySelector(".notify-panel")
      ?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await flush(card);
    expect(card.shadowRoot?.querySelector("form.timer-settings")).toBeNull();
  });

  it("moves focus into the panel on open, and Escape closes it and returns focus", async () => {
    const { card } = await mountTimer(timer());
    await openPanel(card);
    expect(root(card).activeElement?.id).toBe("timer-notify");
    root(card)
      .querySelector(".notify-panel")
      ?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await flush(card);
    expect(root(card).querySelector(".notify-panel")).toBeNull();
    expect(root(card).activeElement?.hasAttribute("data-notify-button")).toBe(true);
  });

  it("focuses the panel itself when there is no checkbox", async () => {
    define(globalThis, "isSecureContext", false);
    const { card } = await mountTimer(timer());
    await openPanel(card);
    expect(root(card).activeElement?.classList.contains("notify-panel")).toBe(true);
  });
});
