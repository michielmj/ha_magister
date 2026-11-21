import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import { formatShortDay } from "./logic";
import { HomeworkSubscription, type LoadError } from "./subscription";
import { effectiveLabel, formatCountdown, metaLine } from "./timer";
import { TimerController } from "./timer-controller";
import {
  renderActions,
  renderLive,
  renderPanel,
  timerStyles,
  type TimerContext,
} from "./timer-views";
import { format, languageOf, textsFor, type Texts } from "./translations";
import type { Hass, HomeworkPayload, TimerCardConfig } from "./types";

const TOAST_MS = 6000;
const RING_RADIUS = 52;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

export interface NormalizedTimerConfig {
  entity: string;
  title: string;
  show_when_idle: boolean;
}

/** Validate a timer card config and fill in the defaults. An empty entity is allowed (the card then asks for one). */
export function normalizeTimerConfig(config: Partial<TimerCardConfig> | undefined): NormalizedTimerConfig {
  if (!config || typeof config !== "object") throw new Error("Invalid configuration");
  const entity = config.entity ?? "";
  if (typeof entity !== "string") throw new Error("entity must be a to-do entity id");
  if (entity !== "" && !entity.startsWith("todo.")) {
    throw new Error("entity must be a to-do entity (todo.*)");
  }
  return {
    entity,
    title: typeof config.title === "string" ? config.title : "",
    show_when_idle: config.show_when_idle !== false,
  };
}

/**
 * The study timer of one child as a card of its own: a large countdown with a ring, the buttons
 * (pause, stop, and Klaar / +x min / Nog niet when time is up) and the question "Hoe ver ben je?".
 * It shares the subscription, the timer logic and the panels with the homework card.
 */
export class MagisterTimerCard extends LitElement {
  static override properties = {
    _payload: { state: true },
    _loadError: { state: true },
    _offline: { state: true },
    _toast: { state: true },
  };

  declare _payload: HomeworkPayload | undefined;
  declare _loadError: LoadError | undefined;
  declare _offline: boolean;
  declare _toast: string;
  /** HA's hui-card removes hidden cards unless this is set. */
  connectedWhileHidden: boolean;

  /** Set by HA's hui-card: the idle card must stay visible while editing. */
  private _preview = false;
  private _editMode = false;
  set preview(value: boolean | undefined) {
    this._preview = value === true;
    this.requestUpdate();
  }
  get preview(): boolean {
    return this._preview;
  }
  set editMode(value: boolean | undefined) {
    this._editMode = value === true;
    this.requestUpdate();
  }
  get editMode(): boolean {
    return this._editMode;
  }

  private _config: NormalizedTimerConfig | undefined;
  private _hass: Hass | undefined;
  private _hassKey = "";
  private _toastTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly _subscription: HomeworkSubscription;
  private readonly _timer: TimerController;

  constructor() {
    super();
    this.connectedWhileHidden = true;
    this._offline = false;
    this._toast = "";
    this._subscription = new HomeworkSubscription({
      isConnected: () => this.isConnected,
      hass: () => this._hass,
      entity: () => this._config?.entity,
      onPayload: (payload) => {
        this._payload = payload;
        this._loadError = undefined;
        this._offline = false;
        this._timer.onPayload();
      },
      onLoadError: (error) => {
        this._loadError = error;
      },
      onOffline: (offline) => {
        this._offline = offline;
      },
      hasLoadError: () => this._loadError !== undefined,
    });
    this._timer = new TimerController(this, {
      hass: () => this._hass,
      entity: () => this._config?.entity,
      payload: () => this._payload,
      canWrite: () => this._payload?.available === true && !this._offline,
      texts: () => this._texts(),
      showError: (message) => {
        this._showToast(message);
      },
      itemLabel: (item) => effectiveLabel(item, this._texts()),
      fallbackFocus: () => [".timer-idle"],
      lockOnDenied: true,
    });
  }

  // -- Home Assistant card API --

  static getConfigElement(): HTMLElement {
    return document.createElement("magister-timer-card-editor");
  }

  static getStubConfig(hass?: Hass): Partial<TimerCardConfig> {
    const entity = Object.entries(hass?.entities ?? {}).find(
      ([entityId, entry]) => entityId.startsWith("todo.") && entry?.platform === "magister",
    )?.[0];
    return { entity: entity ?? "" };
  }

  setConfig(config: Partial<TimerCardConfig>): void {
    const next = normalizeTimerConfig(config);
    if (next.entity !== this._config?.entity) {
      this._subscription.reset();
      this._payload = undefined;
      this._loadError = undefined;
      this._offline = false;
      this._timer.reset();
      this._subscription.resetBackoff();
    }
    this._config = next;
    this.requestUpdate();
    this._subscription.ensure();
  }

  set hass(hass: Hass | undefined) {
    this._hass = hass;
    // Home Assistant sets hass on every state change: render only when it matters.
    const key = `${hass?.locale?.language ?? ""}|${hass?.language ?? ""}`;
    if (key !== this._hassKey || !this._payload) {
      this._hassKey = key;
      this.requestUpdate();
    }
    this._subscription.ensure();
  }

  get hass(): Hass | undefined {
    return this._hass;
  }

  getCardSize(): number {
    return this._hidden() ? 0 : this._timer.view() ? 4 : 2;
  }

  getGridOptions(): Record<string, number> {
    return { columns: 6, min_columns: 3, min_rows: 2 };
  }

  // -- lifecycle --

  override connectedCallback(): void {
    super.connectedCallback();
    this._subscription.ensure();
    this._timer.connected();
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._subscription.reset();
    this._timer.disconnected();
    if (this._toastTimer) clearTimeout(this._toastTimer);
  }

  private _texts(): Texts {
    return textsFor(this._hass?.locale?.language ?? this._hass?.language);
  }

  private _showToast(message: string): void {
    this._toast = message;
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = "";
    }, TOAST_MS);
  }

  /** The card is hidden when there is no timer and `show_when_idle` is off (also while loading). */
  private _hidden(): boolean {
    if (this._config?.show_when_idle !== false || !this._config.entity) return false;
    if (this._loadError || this._preview || this._editMode) return false;
    return this._timer.view() === undefined;
  }

  protected override willUpdate(): void {
    this._timer.willUpdate();
    const hidden = this._hidden();
    if (hidden !== this.hasAttribute("hidden")) {
      this.toggleAttribute("hidden", hidden);
      this.dispatchEvent(
        new CustomEvent("card-visibility-changed", {
          detail: { value: !hidden },
          bubbles: true,
          composed: true,
        }),
      );
    }
  }

  private _context(texts: Texts): TimerContext {
    return {
      controller: this._timer,
      texts,
      language: languageOf(this._hass?.locale?.language ?? this._hass?.language),
      enabled: this._payload?.available === true && !this._offline,
    };
  }

  // -- rendering --

  protected override render(): TemplateResult | typeof nothing {
    if (this._hidden()) return nothing;
    const texts = this._texts();
    return html`<ha-card .header=${this._config?.title ?? ""}>
      ${renderLive(this._context(texts))}
      <div class="content ${this._config?.title ? "titled" : ""}">${this._renderBody(texts)}</div>
      ${this._toast
        ? html`<div class="toast" role="alert">
            <span>${this._toast}</span>
            <button type="button" @click=${() => {
              this._toast = "";
            }}>${texts.dismiss}</button>
          </div>`
        : nothing}
    </ha-card>`;
  }

  private _renderBody(texts: Texts): TemplateResult {
    if (!this._config?.entity) return html`<p class="state">${texts.choose_entity}</p>`;
    if (this._loadError) return html`<p class="state error">${texts[this._loadError]}</p>`;
    if (!this._payload) return html`<p class="state">${texts.loading}</p>`;
    const banner = !this._payload.available
      ? html`<p class="banner" role="status">${texts.unavailable}</p>`
      : this._offline
        ? html`<p class="banner" role="status">${texts.offline}</p>`
        : nothing;
    const context = this._context(texts);
    const view = this._timer.view();
    if (!view) {
      return html`${banner}<p class="state timer-idle" tabindex="-1">${texts.timer.idle}</p>`;
    }
    const lang = context.language === "nl" ? "nl" : "en-GB";
    const meta = metaLine(texts.timer.meta, {
      subject: view.timer.subject,
      label: this._timer.labelOf(view.timer.subtask),
      date: formatShortDay(view.timer.due, lang),
    });
    const stateName = texts.timer[view.state];
    const offset = RING_LENGTH * (1 - view.fraction);
    const long = view.remaining >= 3600;
    return html`${banner}<div class="tc ${view.state}" role="group" aria-label=${texts.timer.region}>
      <div class="ring">
        <svg viewBox="0 0 120 120" aria-hidden="true" focusable="false">
          <circle class="ring-track" cx="60" cy="60" r=${RING_RADIUS}></circle>
          <circle
            class="ring-fill"
            cx="60"
            cy="60"
            r=${RING_RADIUS}
            stroke-dasharray=${RING_LENGTH.toFixed(2)}
            stroke-dashoffset=${offset.toFixed(2)}
            transform="rotate(-90 60 60)"
          ></circle>
        </svg>
        <div class="ring-text">
          <span class="big ${long ? "long" : ""} countdown ${view.state}" role="timer" aria-live="off"
            ><span class="sr-only">${format(texts.timer.countdown_aria, {
              title: view.timer.title,
              state: stateName,
            })}: </span
            >${formatCountdown(view.remaining)}</span
          >
          <span class="state-name ${view.state}">${stateName}</span>
        </div>
      </div>
      <h3 class="tc-title">${view.timer.title}</h3>
      <p class="meta tc-meta">${meta}</p>
      <div class="tc-actions">${renderActions(context, view, "card")}</div>
      ${this._timer.locked
        ? html`<p class="read-only" role="note">${this._timer.lockCode === "unauthorized" ? texts.timer.errors.unauthorized : texts.timer.read_only}</p>`
        : nothing}
      ${renderPanel(context)}
    </div>`;
  }

  static override styles = [
    timerStyles,
    css`
      :host {
        display: block;
      }
      :host([hidden]) {
        display: none;
      }
      ha-card {
        display: block;
        overflow: hidden;
      }
      .content {
        padding: 16px;
      }
      .content.titled {
        padding-top: 0;
      }
      .state {
        margin: 16px 0;
        text-align: center;
        color: var(--secondary-text-color);
        font-size: 1.1em;
      }
      .state.error {
        color: var(--error-color);
      }
      .timer-idle:focus {
        outline: none;
      }
      .banner {
        margin: 0 0 12px;
        padding: 8px 12px;
        border-radius: 8px;
        background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
        color: var(--primary-text-color);
        font-size: 0.9em;
      }
      .tc {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
        text-align: center;
      }
      .ring {
        position: relative;
        width: min(240px, 70%);
        aspect-ratio: 1;
      }
      .ring svg {
        display: block;
        width: 100%;
        height: 100%;
      }
      .ring circle {
        fill: none;
        stroke-width: 9;
      }
      .ring-track {
        stroke: var(--divider-color);
      }
      .ring-fill {
        stroke: var(--timer-color);
        stroke-linecap: round;
      }
      .tc.paused .ring-fill {
        stroke: var(--secondary-text-color);
      }
      .tc.finished .ring-fill {
        stroke: var(--timer-warn);
      }
      .ring-text {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 2px;
      }
      .big {
        font-size: 2.6em;
        line-height: 1.1;
      }
      .big.long {
        font-size: 2em;
      }
      .state-name {
        font-size: 0.95em;
        font-weight: 500;
        color: var(--secondary-text-color);
      }
      .state-name.finished {
        color: var(--primary-text-color);
        font-weight: 700;
      }
      .tc-title {
        margin: 8px 0 0;
        font-size: 1.3em;
        font-weight: 600;
        overflow-wrap: anywhere;
      }
      .tc-meta {
        margin: 0;
        font-size: 0.95em;
        color: var(--secondary-text-color);
      }
      .tc-actions {
        display: flex;
        justify-content: center;
        margin-top: 8px;
      }
      .tc-actions .timer-actions {
        justify-content: center;
        gap: 12px;
      }
      .read-only {
        margin: 8px 0 0;
        padding: 8px 12px;
        border-radius: 8px;
        background: color-mix(in srgb, var(--timer-color) 10%, transparent);
        font-size: 0.9em;
        color: var(--primary-text-color);
      }
      .timer-panel {
        align-self: stretch;
        text-align: left;
      }
      .step {
        min-height: 56px;
        font-size: 1.1em;
      }
      .steps {
        max-width: none;
      }
      .timer-panel-actions button {
        min-height: 52px;
        padding: 0 20px;
        border-radius: 26px;
      }
      .toast {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin: 0 16px 16px;
        padding: 8px 12px;
        border-radius: 8px;
        background: var(--error-color);
        color: var(--text-primary-color, #fff);
        font-size: 0.9em;
      }
      .toast button {
        border: none;
        background: none;
        color: inherit;
        font: inherit;
        font-weight: 700;
        text-decoration: underline;
        cursor: pointer;
      }
      .toast button:focus-visible {
        outline: 2px solid var(--text-primary-color, #fff);
        outline-offset: 2px;
      }
      .meta {
        font-size: 0.8em;
      }
    `,
  ];
}
