import { STEPS, snapToStep } from "./logic";
import {
  NOT_ALLOWED,
  effectiveState,
  elapsedFraction,
  estimateSkew,
  optimisticTimer,
  prewarnThreshold,
  remainingSeconds,
  sameSettings,
  sameTimer,
  settingsOf,
  timerKey,
  validateSettings,
  type SubtaskInfo,
} from "./timer";
import { listen, notifyMoment, onChange } from "./notifications";
import { format, type Texts } from "./translations";
import type {
  Hass,
  HomeworkItem,
  HomeworkPayload,
  StudyTimer,
  Subtask,
  TimerAction,
  TimerResult,
  TimerSettings,
  TimerSettingsResult,
  TimerState,
  WsError,
} from "./types";

export const TIMER = "magister/homework/timer";
export const TIMER_SETTINGS = "magister/homework/timer_settings";
/** How long an announcement stays in the live region. */
const ANNOUNCE_MS = 10_000;
/** The one-shot moment timers fire this long after the moment, so the clock has passed it. */
const MOMENT_SLACK_MS = 50;

/** What the controller needs from the element that owns it. */
export interface TimerHost {
  readonly isConnected: boolean;
  readonly shadowRoot: ShadowRoot | null;
  readonly updateComplete: Promise<unknown>;
  requestUpdate(): void;
}

/** What the controller needs to know about the card around it. */
export interface TimerDeps {
  hass(): Hass | undefined;
  entity(): string | undefined;
  payload(): HomeworkPayload | undefined;
  /** Connected and the data is available: the buttons work. */
  canWrite(): boolean;
  texts(): Texts;
  showError(message: string): void;
  /** The (effective) label of an item, for the optimistic timer. */
  itemLabel?(item: HomeworkItem): string;
  /** Focus targets to try when the timer's own controls have vanished. */
  fallbackFocus?(): string[];
  /**
   * Apply an optimistic progress to a subtask; the returned function settles it (true: the
   * backend accepted it, false: roll it back).
   */
  beginProgress?(uid: string, progress: number): (ok: boolean) => void;
  /** A denial (`not_allowed_for_role`, `unauthorized`) turns the controls off for the rest of the session. */
  lockOnDenied?: boolean;
}

export interface TimerView {
  timer: StudyTimer;
  state: TimerState;
  remaining: number;
  fraction: number;
}

export interface ProgressPanel {
  uid: string;
  selected: number;
}

export interface SettingsForm {
  prewarn: string;
  extra: string;
  error: string;
}

/** The timer of one child: optimistic changes, the countdown, announcements, panels. */
export class TimerController {
  /** The optimistic timer, until the backend has answered. */
  override: { timer: StudyTimer | null } | undefined;
  settingsOverride: TimerSettings | undefined;
  /** The subtask whose start waits for the "replace the running timer?" confirmation. */
  confirmUid: string | undefined;
  panel: ProgressPanel | undefined;
  settingsOpen = false;
  settingsForm: SettingsForm = { prewarn: "", extra: "", error: "" };
  /** The user may not control the timer (a denial was answered): the controls are off. */
  locked = false;
  /** The refusal code that locked the controls. */
  lockCode: string | undefined;
  announcement = "";
  /** The server clock minus this device's clock. */
  skewMs = 0;
  /** The "Meldingen" panel of the timer card is open. */
  notifyOpen = false;

  private _token = 0;
  private _pending: number | undefined;
  private _settingsPending: number | undefined;
  private _ticker: ReturnType<typeof setInterval> | undefined;
  /** One-shot timers for the upcoming moments: a hidden tab throttles the ticker but still runs these. */
  private _moments: ReturnType<typeof setTimeout>[] = [];
  private _visibility: (() => void) | undefined;
  private _announceTimer: ReturnType<typeof setTimeout> | undefined;
  private _unsubscribe: (() => void) | undefined;
  private _seen:
    | {
        key: string;
        prewarnDone: boolean;
        endDone: boolean;
        sawActive: boolean;
        lastRemaining: number | undefined;
      }
    | undefined;

  constructor(
    private readonly host: TimerHost,
    private readonly deps: TimerDeps,
  ) {}

  // -- the data --

  now(): number {
    return Date.now();
  }

  timer(): StudyTimer | null {
    if (this.override) return this.override.timer;
    return this.deps.payload()?.timer ?? null;
  }

  settings(): TimerSettings {
    return this.settingsOverride ?? settingsOf(this.deps.payload()?.timer_settings);
  }

  view(): TimerView | undefined {
    const timer = this.timer();
    if (!timer) return undefined;
    const now = this.now();
    return {
      timer,
      state: effectiveState(timer, now, this.skewMs),
      remaining: remainingSeconds(timer, now, this.skewMs),
      fraction: elapsedFraction(timer, now, this.skewMs),
    };
  }

  /** The timer when it belongs to this subtask. */
  viewFor(uid: string): TimerView | undefined {
    const view = this.view();
    return view?.timer.subtask === uid ? view : undefined;
  }

  /** Can "+x min" be offered: only when the timer has run out and extra minutes are set. */
  extraMinutes(view: TimerView | undefined): number | null {
    return view?.state === "finished" ? this.settings().extra_minutes : null;
  }

  // -- lifecycle --

  /** Another entity: nothing of the old child may stay. */
  reset(): void {
    this.override = undefined;
    this.settingsOverride = undefined;
    this.confirmUid = undefined;
    this.panel = undefined;
    this.settingsOpen = false;
    this.locked = false;
    this.lockCode = undefined;
    this._pending = undefined;
    this._settingsPending = undefined;
    this._seen = undefined;
    this.skewMs = 0;
    this._setAnnouncement("");
    this._arm();
    this.sync();
  }

  connected(): void {
    // The notification settings are per browser: another card or tab may change them.
    listen();
    this._unsubscribe ??= onChange(() => {
      this.host.requestUpdate();
    });
    if (!this._visibility && typeof document !== "undefined") {
      this._visibility = () => {
        this._arm();
        this.observe();
        this.host.requestUpdate();
      };
      document.addEventListener("visibilitychange", this._visibility);
    }
    this._arm();
    this.sync();
  }

  disconnected(): void {
    this._unsubscribe?.();
    this._unsubscribe = undefined;
    if (this._visibility) document.removeEventListener("visibilitychange", this._visibility);
    this._visibility = undefined;
    this._disarm();
    this._stopTicker();
    if (this._announceTimer) clearTimeout(this._announceTimer);
    this._announceTimer = undefined;
  }

  /** A payload arrived: confirmed changes replace the optimistic ones. */
  onPayload(): void {
    if (this._pending === undefined) this.override = undefined;
    if (this._settingsPending === undefined) this.settingsOverride = undefined;
    this._validate();
    this.observe();
    this._arm();
    this.sync();
  }

  // -- the moments --

  private _disarm(): void {
    for (const handle of this._moments) clearTimeout(handle);
    this._moments = [];
  }

  /**
   * One timeout per upcoming moment (the pre-warning and the end), a little after it. A hidden tab throttles
   * the ticker, but a timer made outside a timer task still fires on time. Never called from `tick`: a timer made
   * inside a timer task inherits its chain count and is throttled as well.
   */
  private _arm(): void {
    this._disarm();
    if (!this.host.isConnected) return;
    const view = this.view();
    if (view?.state !== "running" || view.timer.state !== "running") return;
    const delays: number[] = [];
    // What this card has seen wins over the payload: a `prewarned` push just before the local crossing must not
    // cancel the one-shot (the observation still announces the moment).
    const key = timerKey(view.timer);
    const prewarnDone = this._seen?.key === key ? this._seen.prewarnDone : view.timer.prewarned === true;
    const threshold = prewarnDone ? undefined : prewarnThreshold(view.timer, this.settings());
    if (threshold !== undefined && view.remaining > threshold) delays.push((view.remaining - threshold) * 1000);
    delays.push(view.remaining * 1000);
    for (const delay of delays) {
      this._moments.push(
        setTimeout(() => {
          this.observe();
          this.host.requestUpdate();
        }, delay + MOMENT_SLACK_MS),
      );
    }
  }

  /** Panels and confirmations whose target is gone (or that cannot be used now) are closed. */
  private _validate(): void {
    const timer = this.timer();
    if (this.panel && (!timer || timer.subtask !== this.panel.uid)) this.panel = undefined;
    if (this.confirmUid && !this._info(this.confirmUid)) this.confirmUid = undefined;
  }

  /** Call from willUpdate: confirmations and panels cannot stay while the card is read-only. */
  willUpdate(): void {
    if (!this.deps.canWrite()) {
      this.confirmUid = undefined;
    }
    this._validate();
  }

  // -- ticking and announcements --

  /** Tick once a second, only while a timer counts down. */
  sync(): void {
    const view = this.view();
    const counting = view?.state === "running" && view.timer.state === "running";
    if (counting && this.host.isConnected) {
      this._ticker ??= setInterval(() => {
        this.tick();
      }, 1000);
    } else {
      this._stopTicker();
    }
  }

  private _stopTicker(): void {
    if (this._ticker) clearInterval(this._ticker);
    this._ticker = undefined;
  }

  tick(): void {
    this.observe();
    this.host.requestUpdate();
    this.sync();
  }

  get ticking(): boolean {
    return this._ticker !== undefined;
  }

  /**
   * Announce the pre-warning moment and the end (once each, politely): only when the card sees
   * the moment pass, never for a timer that was already past it when the card opened.
   */
  observe(): void {
    const view = this.view();
    if (!view) {
      this._seen = undefined;
      return;
    }
    const { timer, state, remaining } = view;
    const key = timerKey(timer);
    if (this._seen?.key !== key) {
      // A pre-warning that was already sent (or skipped on purpose, as in an extension run) is not announced.
      this._seen = {
        key,
        prewarnDone: timer.prewarned === true,
        endDone: false,
        sawActive: false,
        lastRemaining: undefined,
      };
    }
    const seen = this._seen;
    const texts = this.deps.texts();
    if (state === "running" || state === "paused") {
      seen.sawActive = true;
      seen.endDone = false;
      if (!seen.prewarnDone) {
        const threshold = prewarnThreshold(timer, this.settings());
        // No threshold (the setting is off): not latched, the setting may be switched on while the timer runs.
        if (threshold === undefined) {
          // nothing to announce
        } else if (remaining <= threshold) {
          seen.prewarnDone = true;
          if (state === "running" && seen.lastRemaining !== undefined && seen.lastRemaining > threshold) {
            const n = Math.max(Math.round(threshold / 60), 1);
            this._setAnnouncement(
              format(n === 1 ? texts.timer.announce_prewarn_one : texts.timer.announce_prewarn, {
                n,
                title: timer.title,
              }),
            );
            this._notify(
              "prewarn",
              format(n === 1 ? texts.timer.notify_prewarn_one : texts.timer.notify_prewarn, {
                n,
                what: whatOf(timer),
              }),
            );
          }
        }
      }
    } else {
      // Finished: the pre-warning moment has passed for good.
      seen.prewarnDone = true;
      if (!seen.endDone) {
        seen.endDone = true;
        if (seen.sawActive) {
          this._setAnnouncement(format(texts.timer.announce_end, { title: timer.title }));
          this._notify("end", format(texts.timer.notify_end, { what: whatOf(timer) }));
        }
      }
    }
    seen.lastRemaining = remaining;
  }

  /** The browser notification of a moment (once per browser, if this browser switched them on). */
  private _notify(moment: "prewarn" | "end", text: string): void {
    const timer = this.timer();
    if (!timer) return;
    notifyMoment({
      child: this.deps.entity() ?? "",
      startedAt: timer.started_at,
      endsAt: timer.ends_at,
      moment,
      text,
      language: this.deps.texts().timer.language,
    });
  }

  private _setAnnouncement(text: string): void {
    if (this._announceTimer) clearTimeout(this._announceTimer);
    this._announceTimer = undefined;
    this.announcement = text;
    this.host.requestUpdate();
    if (text !== "") {
      this._announceTimer = setTimeout(() => {
        this.announcement = "";
        this._announceTimer = undefined;
        this.host.requestUpdate();
      }, ANNOUNCE_MS);
    }
  }

  // -- subtasks --

  private _find(uid: string): { subtask: Subtask; item: HomeworkItem } | undefined {
    for (const item of this.deps.payload()?.items ?? []) {
      const subtask = item.subtasks?.find((candidate) => candidate.uid === uid);
      if (subtask) return { subtask, item };
    }
    return undefined;
  }

  private _info(uid: string): SubtaskInfo | undefined {
    const found = this._find(uid);
    if (!found || typeof found.subtask.minutes !== "number") return undefined;
    return {
      uid,
      title: found.subtask.title,
      minutes: found.subtask.minutes,
      subject: found.item.subject,
      due: found.item.date,
      label: this.deps.itemLabel?.(found.item) ?? found.item.label ?? "",
    };
  }

  /** The effective, translated label of the timer's item (the timer's own label when it is not in the payload). */
  labelOf(uid: string): string {
    const fallback = this.view()?.timer.label ?? "";
    const found = this._find(uid);
    if (!found) return fallback;
    return this.deps.itemLabel?.(found.item) ?? found.item.label ?? fallback;
  }

  /** The progress of the timer's subtask (the panel preselects it). */
  progressOf(uid: string): number {
    return this._find(uid)?.subtask.progress ?? 0;
  }

  /** Controls are off: no connection, no data, or a denial was answered. */
  get disabled(): boolean {
    return !this.deps.canWrite() || this.locked;
  }

  // -- actions --

  /** The ▶ button of a subtask: confirm first when another timer runs or is paused. */
  start(uid: string, where: string, replace = false): void {
    if (this.disabled) return;
    const info = this._info(uid);
    if (!info) return;
    const current = this.view();
    const busy = current !== undefined && current.state !== "finished";
    if (busy && !replace) {
      this.confirmUid = uid;
      this.host.requestUpdate();
      this._focus([`.timer-confirm [data-timer-cancel]`]);
      return;
    }
    this.confirmUid = undefined;
    const next = optimisticTimer("start", current?.timer ?? null, this.now(), {
      info,
      skewMs: this.skewMs,
    });
    void this._run(
      "start",
      { subtask: uid, ...(busy ? { replace: true } : {}) },
      next,
      {
        focus: [timerSelector("pause", uid, where), timerSelector("pause", uid, "bar")],
        onResult: (timer, receivedMs) => {
          const skew = estimateSkew(timer, receivedMs);
          if (skew !== undefined) this.skewMs = skew;
        },
      },
    );
  }

  cancelConfirm(uid: string): void {
    this.confirmUid = undefined;
    this.host.requestUpdate();
    this._focus([`[data-timer-start="${cssEscape(uid)}"]`]);
  }

  pause(where: string): void {
    const view = this.view();
    if (this.disabled || view?.state !== "running") return;
    const next = optimisticTimer("pause", view.timer, this.now(), { secondsLeft: view.remaining });
    void this._run("pause", {}, next, {
      focus: [timerSelector("resume", view.timer.subtask, where)],
    });
  }

  resume(where: string): void {
    const view = this.view();
    if (this.disabled || view?.state !== "paused") return;
    const next = optimisticTimer("resume", view.timer, this.now(), { skewMs: this.skewMs });
    void this._run("resume", {}, next, {
      focus: [timerSelector("pause", view.timer.subtask, where)],
    });
  }

  /** "+x min": only when the timer has run out and the student set extra minutes. */
  extend(where: string): void {
    const view = this.view();
    const extra = this.settings().extra_minutes;
    if (this.disabled || view?.state !== "finished" || !extra) return;
    const next = optimisticTimer("extend", view.timer, this.now(), { extra, skewMs: this.skewMs });
    void this._run("extend", {}, next, {
      focus: [timerSelector("pause", view.timer.subtask, where), timerSelector("pause", view.timer.subtask, "bar")],
    });
  }

  /** Klaar: the subtask is done and the timer is gone. */
  done(): void {
    const view = this.view();
    if (this.disabled || view?.state !== "finished") return;
    const uid = view.timer.subtask;
    void this._run("done", {}, null, { progress: { uid, value: 100 }, focus: this._afterFocus(uid) });
  }

  /** Stop and "Nog niet" open the panel "Hoe ver ben je?". */
  openPanel(): void {
    const view = this.view();
    if (this.disabled || !view) return;
    const uid = view.timer.subtask;
    this.settingsOpen = false;
    this.panel = { uid, selected: snapToStep(this.progressOf(uid)) };
    this.host.requestUpdate();
    this._focus([`.timer-panel [role="radio"][tabindex="0"]`]);
  }

  selectStep(value: number): void {
    if (!this.panel || !(STEPS as readonly number[]).includes(value)) return;
    this.panel = { ...this.panel, selected: value };
    this.host.requestUpdate();
    this._focus([`.timer-panel [role="radio"][tabindex="0"]`]);
  }

  closePanel(): void {
    if (!this.panel) return;
    this.panel = undefined;
    this.host.requestUpdate();
    this._focus([`[data-timer-act="stop"]`, `[data-timer-act="not_yet"]`]);
  }

  /** "Opslaan en stoppen" (with the chosen progress) or "Stoppen zonder voortgang". */
  stop(withProgress: boolean): void {
    const panel = this.panel;
    const view = this.view();
    if (this.disabled || !panel || !view || view.timer.subtask !== panel.uid) return;
    this.panel = undefined;
    void this._run(
      "stop",
      withProgress ? { progress: panel.selected } : {},
      null,
      {
        ...(withProgress ? { progress: { uid: panel.uid, value: panel.selected } } : {}),
        focus: this._afterFocus(panel.uid),
      },
    );
  }

  private _afterFocus(uid: string): string[] {
    return [`[data-timer-start="${cssEscape(uid)}"]`, ...(this.deps.fallbackFocus?.() ?? [])];
  }

  private async _run(
    action: TimerAction,
    params: Record<string, unknown>,
    next: StudyTimer | null,
    options: {
      progress?: { uid: string; value: number };
      focus?: string[];
      onResult?: (timer: StudyTimer | null, receivedMs: number) => void;
    },
  ): Promise<void> {
    const hass = this.deps.hass();
    const entity = this.deps.entity();
    if (!hass || !entity) return;
    const token = ++this._token;
    this._pending = token;
    this.override = { timer: next };
    const settle = options.progress
      ? this.deps.beginProgress?.(options.progress.uid, options.progress.value)
      : undefined;
    this.host.requestUpdate();
    this.observe();
    this._arm();
    this.sync();
    if (options.focus) this._focus(options.focus);
    try {
      const result = await hass.callWS<TimerResult>({
        type: TIMER,
        entity_id: entity,
        action,
        ...params,
      });
      settle?.(true);
      if (this._pending !== token) return;
      this._pending = undefined;
      options.onResult?.(result.timer, this.now());
      // The push usually arrived first; otherwise keep the confirmed timer until it does.
      if (sameTimer(this.deps.payload()?.timer, result.timer)) this.override = undefined;
      else this.override = { timer: result.timer };
    } catch (error) {
      settle?.(false);
      if (this._pending !== token) return;
      this._pending = undefined;
      this.override = undefined;
      const code = (error as WsError | undefined)?.code;
      this._fail(code);
    }
    this.host.requestUpdate();
    this.observe();
    this._arm();
    this.sync();
  }

  private _fail(code: string | undefined): void {
    const errors = this.deps.texts().timer.errors;
    if (code !== undefined && NOT_ALLOWED.has(code) && this.deps.lockOnDenied === true) {
      this.locked = true;
      this.lockCode = code;
    }
    this.deps.showError((code ? errors[code] : undefined) ?? errors.default ?? "");
  }

  // -- settings --

  openSettings(): void {
    const settings = this.settings();
    this.panel = undefined;
    this.settingsForm = {
      prewarn: settings.prewarn_minutes === null ? "" : String(settings.prewarn_minutes),
      extra: settings.extra_minutes === null ? "" : String(settings.extra_minutes),
      error: "",
    };
    this.settingsOpen = true;
    this.host.requestUpdate();
    this._focus([`.timer-settings select`]);
  }

  closeSettings(): void {
    this.settingsOpen = false;
    this.host.requestUpdate();
    this._focus([`[data-timer-settings-button]`]);
  }

  patchSettings(patch: Partial<SettingsForm>): void {
    this.settingsForm = { ...this.settingsForm, ...patch, error: "" };
    this.host.requestUpdate();
  }

  async saveSettings(): Promise<void> {
    const hass = this.deps.hass();
    const entity = this.deps.entity();
    if (this.disabled || !hass || !entity || !this.settingsOpen) return;
    const form = this.settingsForm;
    const checked = validateSettings({ prewarn_minutes: form.prewarn, extra_minutes: form.extra });
    const errors = this.deps.texts().timer.errors;
    if (!checked.ok) {
      this.settingsForm = { ...form, error: errors.invalid_format ?? "" };
      this.host.requestUpdate();
      return;
    }
    const wanted = checked.settings;
    // Nothing changed: nothing to send.
    if (sameSettings(wanted, this.settings())) {
      this.closeSettings();
      return;
    }
    const token = ++this._token;
    this._settingsPending = token;
    this.settingsOverride = wanted;
    this.settingsOpen = false;
    this.host.requestUpdate();
    this.observe();
    this._arm();
    this._focus([`[data-timer-settings-button]`]);
    try {
      const result = await hass.callWS<TimerSettingsResult>({
        type: TIMER_SETTINGS,
        entity_id: entity,
        prewarn_minutes: wanted.prewarn_minutes,
        extra_minutes: wanted.extra_minutes,
      });
      if (this._settingsPending !== token) return;
      this._settingsPending = undefined;
      const stored = settingsOf(result.timer_settings);
      if (sameSettings(settingsOf(this.deps.payload()?.timer_settings), stored)) {
        this.settingsOverride = undefined;
      } else {
        this.settingsOverride = stored;
      }
    } catch (error) {
      if (this._settingsPending !== token) return;
      this._settingsPending = undefined;
      this.settingsOverride = undefined;
      const code = (error as WsError | undefined)?.code;
      if (code !== undefined && NOT_ALLOWED.has(code) && this.deps.lockOnDenied === true) {
        this.locked = true;
        this.lockCode = code;
      }
      // Back in the panel with the reason, so the input is not lost.
      this.settingsForm = { ...form, error: (code ? errors[code] : undefined) ?? errors.default ?? "" };
      this.settingsOpen = true;
      this._focus([`.timer-settings .timer-error`, `.timer-settings select`]);
    }
    this.host.requestUpdate();
    this.observe();
    this._arm();
  }

  /** After a render: the selects show the form's values (the options are rendered after the select is set). */
  afterRender(): void {
    if (!this.settingsOpen) return;
    const form = this.settingsForm;
    for (const [selector, wanted] of [
      ["#timer-prewarn", form.prewarn],
      ["#timer-extra", form.extra],
    ] as const) {
      const select = this.host.shadowRoot?.querySelector<HTMLSelectElement>(selector);
      if (select && select.value !== wanted) select.value = wanted;
    }
  }

  // -- focus --

  private _focus(selectors: string[]): void {
    void this.host.updateComplete.then(() => {
      for (const selector of selectors) {
        const element = this.host.shadowRoot?.querySelector<HTMLElement>(selector);
        if (element) {
          element.focus();
          return;
        }
      }
    });
  }
}

/** "title (subject)", or the title alone when the subject is empty. */
function whatOf(timer: StudyTimer): string {
  return timer.subject ? `${timer.title} (${timer.subject})` : timer.title;
}

/** The selector of one timer button: its action, the subtask and where it sits ("row", "bar", "card"). */
export function timerSelector(act: string, uid: string, where: string): string {
  return `[data-timer-act="${act}"][data-timer-uid="${cssEscape(uid)}"][data-timer-where="${where}"]`;
}

function cssEscape(value: string): string {
  return typeof CSS !== "undefined" && typeof CSS.escape === "function"
    ? CSS.escape(value)
    : value.replace(/["\\]/g, "\\$&");
}
