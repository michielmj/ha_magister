/**
 * Browser notifications for the study timer (1.10.1).
 *
 * Per browser, not per child: the settings live in `localStorage` and nothing goes to the backend. The cards on the
 * page and in other tabs share one claim per moment (child + `started_at` + moment), so a moment notifies once.
 */

const SETTINGS_KEY = "magister.notifications";
const CLAIM_PREFIX = "magister.notify.claim.";
const CHANNEL = "magister-notifications";
/** Old claims are cleaned up after this long (a moment is never claimed twice anyway). */
const CLAIM_TTL_MS = 24 * 3600_000;

export interface NotifySettings {
  enabled: boolean;
  sound: boolean;
}

/** Why the option is not available in this browser, or "ok". */
export type Availability = "ok" | "unsupported" | "insecure" | "app";

export type Moment = "prewarn" | "end";

export interface MomentInfo {
  /** The child (the to-do entity of the list). */
  child: string;
  startedAt: string;
  /** The end of the current run: an extension changes it, so the new end notifies again. */
  endsAt: string | undefined;
  moment: Moment;
  /** The notification text, already translated. */
  text: string;
  language: string;
}

// -- localStorage, always guarded --

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string): boolean {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

// -- settings --

export function readSettings(): NotifySettings {
  const raw = readStorage(SETTINGS_KEY);
  if (raw !== null) {
    try {
      const parsed = JSON.parse(raw) as Partial<NotifySettings> | null;
      return { enabled: parsed?.enabled === true, sound: parsed?.sound !== false };
    } catch {
      // fall through to the defaults
    }
  }
  return { enabled: false, sound: true };
}

const listeners = new Set<() => void>();

/** Be told when the settings (or the permission) change, here or in another tab. */
export function onChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function emit(): void {
  for (const listener of [...listeners]) listener();
}

/** A failing `localStorage` keeps the choice for this page only. */
let memory: NotifySettings | undefined;

function saveSettings(settings: NotifySettings): void {
  memory = settings;
  writeStorage(SETTINGS_KEY, JSON.stringify(settings));
  emit();
}

export function currentSettings(): NotifySettings {
  if (readStorage(SETTINGS_KEY) === null && memory) return memory;
  return readSettings();
}

if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
  window.addEventListener("storage", (event) => {
    if (event.key === SETTINGS_KEY || event.key === null) emit();
  });
}

// -- what this browser can do --

export function availability(): Availability {
  if (typeof window === "undefined") return "unsupported";
  if (typeof navigator !== "undefined" && navigator.userAgent.includes("Home Assistant/")) return "app";
  if (typeof window.Notification === "undefined") return "unsupported";
  if (!window.isSecureContext) return "insecure";
  return "ok";
}

export type Permission = NotificationPermission | "unsupported";

export function permission(): Permission {
  return typeof window !== "undefined" && typeof window.Notification !== "undefined"
    ? window.Notification.permission
    : "unsupported";
}

export interface NotifyState {
  availability: Availability;
  permission: Permission;
  /** Switched on and allowed by the browser: notifications will be shown. */
  active: boolean;
  sound: boolean;
}

export function notifyState(): NotifyState {
  const available = availability();
  const allowed = permission();
  const settings = currentSettings();
  return {
    availability: available,
    permission: allowed,
    active: available === "ok" && allowed === "granted" && settings.enabled,
    sound: settings.sound,
  };
}

/**
 * Switch the notifications on or off. Switching on must be called from a click: it asks the browser for permission.
 */
export async function setEnabled(on: boolean): Promise<void> {
  if (!on) {
    saveSettings({ ...currentSettings(), enabled: false });
    return;
  }
  if (availability() !== "ok") return;
  unlockAudio();
  let result: NotificationPermission = window.Notification.permission;
  if (result === "default") {
    try {
      result = await window.Notification.requestPermission();
    } catch {
      result = window.Notification.permission;
    }
  }
  saveSettings({ ...currentSettings(), enabled: result === "granted" });
}

export function setSound(on: boolean): void {
  saveSettings({ ...currentSettings(), sound: on });
  if (on) unlockAudio();
}

// -- sound --

let audio: AudioContext | undefined;

type AudioConstructor = new () => AudioContext;

function audioContext(): AudioContext | undefined {
  if (audio) return audio;
  try {
    const win = window as unknown as { AudioContext?: AudioConstructor; webkitAudioContext?: AudioConstructor };
    const Ctor = win.AudioContext ?? win.webkitAudioContext;
    if (!Ctor) return undefined;
    audio = new Ctor();
  } catch {
    audio = undefined;
  }
  return audio;
}

/** Called from a click, so the browser allows sound later. */
function unlockAudio(): void {
  try {
    const context = audioContext();
    if (context?.state === "suspended") void context.resume().catch(() => undefined);
  } catch {
    // no sound, no problem
  }
}

/** A short, soft double beep. Silently skipped when the browser does not allow sound. */
export function playTone(): void {
  try {
    const context = audioContext();
    if (!context) return;
    if (context.state === "suspended") void context.resume().catch(() => undefined);
    const start = context.currentTime;
    for (const [offset, frequency] of [
      [0, 880],
      [0.22, 1175],
    ] as const) {
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, start + offset);
      gain.gain.exponentialRampToValueAtTime(0.25, start + offset + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + offset + 0.18);
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.start(start + offset);
      oscillator.stop(start + offset + 0.2);
    }
  } catch {
    // blocked or unsupported: silently skipped
  }
}

// -- one notification per moment --

const claimed = new Set<string>();
let channel: BroadcastChannel | undefined;
/** Identifies this page in the claims. */
const PAGE_ID = Math.random().toString(36).slice(2);

function openChannel(): BroadcastChannel | undefined {
  if (channel) return channel;
  try {
    if (typeof BroadcastChannel === "undefined") return undefined;
    channel = new BroadcastChannel(CHANNEL);
    channel.onmessage = (event: MessageEvent) => {
      const data = event.data as { claim?: unknown } | null;
      if (typeof data?.claim === "string") claimed.add(data.claim);
    };
  } catch {
    channel = undefined;
  }
  return channel;
}

/** Hear the claims of other tabs from now on. */
export function listen(): void {
  openChannel();
}

export function momentId(info: Pick<MomentInfo, "child" | "startedAt" | "endsAt" | "moment">): string {
  const parts = [info.child, info.startedAt, info.moment];
  if (info.moment === "end") parts.push(info.endsAt ?? "");
  return parts.join("|");
}

function pruneClaims(): void {
  try {
    const now = Date.now();
    const stale: string[] = [];
    for (let index = 0; index < window.localStorage.length; index++) {
      const key = window.localStorage.key(index);
      if (!key?.startsWith(CLAIM_PREFIX)) continue;
      const stamp = Number(window.localStorage.getItem(key)?.split("|")[1]);
      if (!Number.isFinite(stamp) || now - stamp > CLAIM_TTL_MS) stale.push(key);
    }
    for (const key of stale) window.localStorage.removeItem(key);
  } catch {
    // nothing to clean
  }
}

/** Claim a moment for this browser: true for the one page that may show it. */
export function claim(id: string): boolean {
  if (claimed.has(id)) return false;
  claimed.add(id);
  const key = CLAIM_PREFIX + id;
  const mine = `${PAGE_ID}|${Date.now()}`;
  if (readStorage(key) !== null) return false;
  if (writeStorage(key, mine) && readStorage(key) !== mine) return false;
  pruneClaims();
  try {
    openChannel()?.postMessage({ claim: id });
  } catch {
    // the claim in localStorage is enough
  }
  return true;
}

/** Show the notification of a moment, if this browser has them on and nobody else has shown it yet. */
export function notifyMoment(info: MomentInfo): void {
  try {
    openChannel();
    if (!notifyState().active) return;
    if (!claim(momentId(info))) return;
    const { sound } = currentSettings();
    const notification = new window.Notification(info.text, {
      tag: `magister-timer-${info.child}`,
      lang: info.language,
    });
    notification.onclick = () => {
      try {
        window.focus();
      } finally {
        notification.close();
      }
    };
    if (sound) playTone();
  } catch {
    // a browser that refuses (for example Chrome on Android without a service worker) simply shows nothing
  }
}

/** Test helper: forget all claims and the sound of this page. */
export function resetNotificationsForTests(): void {
  claimed.clear();
  memory = undefined;
  audio = undefined;
  channel?.close();
  channel = undefined;
}
