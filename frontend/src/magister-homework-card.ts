import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import {
  STEPS,
  applyOverlay,
  filterItems,
  formatDay,
  groupByDay,
  PROGRESS_PERIODS,
  barPercent,
  normalizeConfig,
  optimisticOverlay,
  snapToStep,
  todayIso,
  toggleTarget,
  type DayGroup,
  type NormalizedConfig,
  type Overlay,
} from "./logic";
import { format, languageOf, textsFor, typeLabel, type Texts } from "./translations";
import type {
  CardConfig,
  Hass,
  HassConnection,
  HomeworkItem,
  HomeworkPayload,
  SetProgressResult,
  Unsubscribe,
  WsError,
} from "./types";

const SUBSCRIBE = "magister/homework/subscribe";
const SET_PROGRESS = "magister/homework/set_progress";
const TOAST_MS = 6000;
/** Retry of a failed subscribe: 30 s, doubling, at most 10 minutes. */
const RETRY_START_MS = 30_000;
const RETRY_MAX_MS = 600_000;

type LoadError = "not_found" | "unauthorized" | "load_failed";

const PAPERCLIP =
  "M16.5,6V17.5A4,4 0 0,1 12.5,21.5A4,4 0 0,1 8.5,17.5V5A2.5,2.5 0 0,1 11,2.5A2.5,2.5 0 0,1 13.5,5V15.5A1,1 0 0,1 12.5,16.5A1,1 0 0,1 11.5,15.5V6H10V15.5A2.5,2.5 0 0,0 12.5,18A2.5,2.5 0 0,0 15,15.5V5A4,4 0 0,0 11,1A4,4 0 0,0 7,5V17.5A5.5,5.5 0 0,0 12.5,23A5.5,5.5 0 0,0 18,17.5V6H16.5Z";

/** Unsubscribe without letting a rejected promise escape. */
function safeUnsubscribe(unsubscribe: Unsubscribe): void {
  try {
    void Promise.resolve(unsubscribe()).catch(() => undefined);
  } catch {
    // already closed
  }
}

export class MagisterHomeworkCard extends LitElement {
  static override properties = {
    _payload: { state: true },
    _loadError: { state: true },
    _offline: { state: true },
    _overlay: { state: true },
    _expanded: { state: true },
    _toast: { state: true },
  };

  declare _payload: HomeworkPayload | undefined;
  declare _loadError: LoadError | undefined;
  declare _offline: boolean;
  declare _overlay: ReadonlyMap<string, Overlay>;
  declare _expanded: ReadonlySet<string>;
  declare _toast: string;

  private _config: NormalizedConfig | undefined;
  private _hass: Hass | undefined;
  private _connection: HassConnection | undefined;
  private _subscribedEntity = "";
  private _unsubscribe: Unsubscribe | undefined;
  private _generation = 0;
  /** The request that last changed an item: only its outcome touches the view. */
  private readonly _tokens = new Map<string, number>();
  private _nextToken = 0;
  private _retryTimer: ReturnType<typeof setTimeout> | undefined;
  private _retryDelay = RETRY_START_MS;
  private _hassKey = "";
  private _dayTimer: ReturnType<typeof setInterval> | undefined;
  private _shownDay = "";
  /** Items ticked off in this view: they stay visible until the card is reloaded. */
  private readonly _touched = new Set<string>();
  private _toastTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly _onDisconnected = () => {
    this._offline = true;
  };
  private readonly _onReady = () => {
    this._offline = false;
    // A reconnect: try again at once after a failed subscribe (a working one is
    // resubscribed by the connection itself).
    if (this._loadError) this._retry();
  };

  constructor() {
    super();
    this._offline = false;
    this._overlay = new Map();
    this._expanded = new Set();
    this._toast = "";
  }

  // -- Home Assistant card API --

  static getConfigElement(): HTMLElement {
    return document.createElement("magister-homework-card-editor");
  }

  static getStubConfig(hass?: Hass): Partial<CardConfig> {
    const entity = Object.entries(hass?.entities ?? {}).find(
      ([entityId, entry]) => entityId.startsWith("todo.") && entry?.platform === "magister",
    )?.[0];
    return { entity: entity ?? "" };
  }

  setConfig(config: Partial<CardConfig>): void {
    const next = normalizeConfig(config);
    if (next.entity !== this._config?.entity) {
      // Another child: nothing of the old list may stay on screen.
      this._resetSubscription();
      this._payload = undefined;
      this._loadError = undefined;
      this._offline = false;
      this._overlay = new Map();
      this._expanded = new Set();
      this._tokens.clear();
      this._touched.clear();
      this._retryDelay = RETRY_START_MS;
    }
    this._config = next;
    this.requestUpdate();
    this._ensureSubscription();
  }

  set hass(hass: Hass | undefined) {
    this._hass = hass;
    // Home Assistant sets hass on every state change: render only when it matters.
    const key = `${hass?.locale?.language ?? ""}|${hass?.language ?? ""}|${hass?.config?.time_zone ?? ""}`;
    if (key !== this._hassKey || !this._payload) {
      this._hassKey = key;
      this.requestUpdate();
    }
    this._ensureSubscription();
  }

  get hass(): Hass | undefined {
    return this._hass;
  }

  getCardSize(): number {
    const items = this._visibleItems().length;
    return items === 0 ? 3 : 2 + items * 2;
  }

  getGridOptions(): Record<string, number> {
    return { columns: 12, min_columns: 6, min_rows: 3 };
  }

  // -- lifecycle --

  override connectedCallback(): void {
    super.connectedCallback();
    this._ensureSubscription();
    // Re-render when the day changes while the dashboard stays open.
    this._dayTimer = setInterval(() => {
      if (this._currentDay() !== this._shownDay) this.requestUpdate();
    }, 60_000);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._resetSubscription();
    if (this._toastTimer) clearTimeout(this._toastTimer);
    if (this._dayTimer) clearInterval(this._dayTimer);
    this._dayTimer = undefined;
  }

  // -- subscription --

  private _ensureSubscription(): void {
    const hass = this._hass;
    const entity = this._config?.entity;
    if (!this.isConnected || !hass?.connection || !entity) return;
    // Also after a failed subscribe: that is retried on reconnect or after a back-off,
    // not on every hass update.
    if (this._subscribedEntity === entity && this._connection === hass.connection) return;
    this._resetSubscription();
    this._attach(hass.connection);
    this._subscribedEntity = entity;
    const generation = ++this._generation;
    hass.connection
      .subscribeMessage<HomeworkPayload>(
        (payload) => {
          if (generation === this._generation) this._onPayload(payload);
        },
        { type: SUBSCRIBE, entity_id: entity },
        { resubscribe: true },
      )
      .then(
        (unsubscribe) => {
          if (generation === this._generation) {
            this._unsubscribe = unsubscribe;
          } else {
            safeUnsubscribe(unsubscribe);
          }
        },
        (error: unknown) => {
          if (generation !== this._generation) return;
          const code = (error as WsError | undefined)?.code;
          this._loadError =
            code === "not_found" || code === "invalid_format"
              ? "not_found"
              : code === "unauthorized"
                ? "unauthorized"
                : "load_failed";
          this._scheduleRetry();
        },
      );
  }

  private _scheduleRetry(): void {
    if (this._retryTimer) clearTimeout(this._retryTimer);
    this._retryTimer = setTimeout(() => {
      this._retryTimer = undefined;
      this._retry();
    }, this._retryDelay);
    this._retryDelay = Math.min(this._retryDelay * 2, RETRY_MAX_MS);
  }

  private _retry(): void {
    this._resetSubscription();
    this._ensureSubscription();
  }

  private _attach(connection: HassConnection): void {
    connection.addEventListener?.("disconnected", this._onDisconnected);
    connection.addEventListener?.("ready", this._onReady);
    this._connection = connection;
    if (connection.connected === false) this._offline = true;
  }

  /** Unsubscribe (also while the subscribe call is still pending) and forget the connection. */
  private _resetSubscription(): void {
    this._generation++;
    if (this._unsubscribe) safeUnsubscribe(this._unsubscribe);
    this._unsubscribe = undefined;
    if (this._retryTimer) clearTimeout(this._retryTimer);
    this._retryTimer = undefined;
    this._connection?.removeEventListener?.("disconnected", this._onDisconnected);
    this._connection?.removeEventListener?.("ready", this._onReady);
    this._connection = undefined;
    this._subscribedEntity = "";
  }

  private _onPayload(payload: HomeworkPayload): void {
    this._payload = payload;
    this._loadError = undefined;
    this._retryDelay = RETRY_START_MS;
    this._offline = false;
    // Confirmed overlays are replaced by the pushed state; requests still in flight stay.
    const kept = new Map<string, Overlay>();
    for (const [uid, overlay] of this._overlay) {
      if (this._tokens.has(uid)) kept.set(uid, overlay);
    }
    this._overlay = kept;
  }

  // -- progress --

  private async _setProgress(uid: string, progress: number): Promise<void> {
    const hass = this._hass;
    const entity = this._config?.entity;
    const source = this._payload?.items.find((candidate) => candidate.uid === uid);
    if (!hass || !entity || !source || !this._payload?.available || this._offline) return;
    const token = ++this._nextToken;
    this._tokens.set(uid, token);
    if (progress >= 100) this._touched.add(uid);
    const shown = applyOverlay([source], this._overlay)[0] ?? source;
    const optimistic = optimisticOverlay(shown, progress);
    this._overlay = new Map(this._overlay).set(uid, optimistic);
    try {
      const stored = await hass.callWS<SetProgressResult>({
        type: SET_PROGRESS,
        entity_id: entity,
        item: uid,
        progress,
      });
      if (this._tokens.get(uid) !== token) return;
      this._tokens.delete(uid);
      const current = this._payload.items.find((item) => item.uid === uid);
      const next = new Map(this._overlay);
      if (current?.progress === stored.progress) {
        next.delete(uid);
      } else {
        next.set(uid, { ...optimistic, progress: stored.progress, completed: stored.completed });
      }
      this._overlay = next;
    } catch (error) {
      // An older request that failed must not undo or announce anything.
      if (this._tokens.get(uid) !== token) return;
      this._tokens.delete(uid);
      const next = new Map(this._overlay);
      next.delete(uid);
      this._overlay = next;
      const code = (error as WsError | undefined)?.code;
      const texts = this._texts();
      this._showToast(code === "unauthorized" ? texts.save_unauthorized : texts.save_failed);
    }
  }

  private _showToast(message: string): void {
    this._toast = message;
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = "";
    }, TOAST_MS);
  }

  private _toggleExpanded(uid: string): void {
    const next = new Set(this._expanded);
    if (!next.delete(uid)) next.add(uid);
    this._expanded = next;
  }

  // -- view model --

  private _language(): string {
    return this._hass?.locale?.language ?? this._hass?.language ?? "en";
  }

  private _texts(): Texts {
    return textsFor(this._language());
  }

  /** Today in the Home Assistant time zone; no side effects. */
  private _currentDay(): string {
    return todayIso(new Date(), this._hass?.config?.time_zone);
  }

  /** Today for rendering; remembers the day that is on screen. */
  private _today(): string {
    this._shownDay = this._currentDay();
    return this._shownDay;
  }

  private _visibleItems(): HomeworkItem[] {
    const config = this._config;
    if (!config || !this._payload) return [];
    return filterItems(applyOverlay(this._payload.items, this._overlay), {
      showCompleted: config.show_completed,
      showPast: config.show_past,
      daysAhead: config.days_ahead,
      today: this._today(),
      keep: this._touched,
    });
  }

  private _dayTitle(group: DayGroup, texts: Texts): string {
    if (group.kind === "today") return texts.today;
    if (group.kind === "tomorrow") return texts.tomorrow;
    return formatDay(group.date, languageOf(this._language()) === "nl" ? "nl" : "en-GB");
  }

  // -- rendering --

  protected override render(): TemplateResult {
    const config = this._config;
    const texts = this._texts();
    return html`<ha-card .header=${config?.title ?? ""}>
      <div class="content ${config?.title ? "titled" : ""}">${this._renderBody(texts)}</div>
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
    const available = this._payload.available;
    const enabled = available && !this._offline;
    const groups = groupByDay(this._visibleItems(), this._today());
    const bars = this._renderBars(texts);
    const banners = html`${bars}${!available
      ? html`<p class="banner" role="status">${texts.unavailable}</p>`
      : nothing}${this._offline
      ? html`<p class="banner" role="status">${texts.offline}</p>`
      : nothing}`;
    if (groups.length === 0) {
      return available
        ? html`${banners}<p class="state empty">${texts.no_homework}</p>`
        : html`${banners}`;
    }
    const firstPast = groups.findIndex((group) => group.kind === "past");
    return html`${banners}<div class="days ${available ? "" : "stale"}">
        ${groups.map(
          (group, index) => html`
            ${index === firstPast
              ? html`<h3 class="section">${texts.earlier}</h3>`
              : nothing}
            <section class="day" aria-labelledby="day-${group.date}">
              <h4 id="day-${group.date}" class=${group.kind}>${this._dayTitle(group, texts)}</h4>
              <ul>
                ${group.items.map((item) => this._renderItem(item, texts, enabled))}
              </ul>
            </section>
          `,
        )}
      </div>`;
  }

  /** The progress bars of the enabled periods (the values come from the progress sensors). */
  private _renderBars(texts: Texts): TemplateResult | typeof nothing {
    const config = this._config;
    const progress = this._payload?.progress;
    const periods = PROGRESS_PERIODS.filter(({ option }) => config?.[option]);
    if (periods.length === 0) return nothing;
    return html`<div class="bars">
      ${periods.map(({ period }) => {
        const label = texts.progress_label[period];
        const entry = progress?.[period] ?? null;
        if (!entry) {
          return html`<div class="bar unavailable">
            <div class="bar-head"><span>${label}</span></div>
            <div
              class="track"
              role="progressbar"
              aria-label=${label}
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuetext=${texts.progress_unavailable}
            ></div>
            <div class="bar-note">${texts.progress_unavailable}</div>
          </div>`;
        }
        const percent = barPercent(entry);
        const value = format(texts.percent, { n: percent });
        const note =
          entry.items === 0
            ? texts.progress_empty
            : format(texts.progress_done, { completed: entry.completed, items: entry.items });
        return html`<div class="bar">
          <div class="bar-head"><span>${label}</span><span class="bar-value">${value}</span></div>
          <div
            class="track"
            role="progressbar"
            aria-label=${label}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow=${percent}
            aria-valuetext="${value}, ${note}"
          >
            <div class="fill" style="width: ${percent}%"></div>
          </div>
          <div class="bar-note">${note}</div>
        </div>`;
      })}
    </div>`;
  }

  private _renderItem(item: HomeworkItem, texts: Texts, enabled: boolean): TemplateResult {
    const expanded = this._expanded.has(item.uid);
    const label = typeLabel(texts, item.info_type, item.label);
    const classes = [
      "item",
      item.is_test ? "test" : "",
      item.completed ? "done" : "",
      item.cancelled ? "cancelled" : "",
    ]
      .filter(Boolean)
      .join(" ");
    return html`<li class=${classes}>
      <input
        type="checkbox"
        .checked=${item.completed}
        ?disabled=${!enabled}
        aria-label=${format(item.completed ? texts.mark_open : texts.mark_done, {
          subject: item.subject,
        })}
        @change=${() => void this._setProgress(item.uid, toggleTarget(item))}
      />
      <div class="main">
        <div class="head">
          <span class="chip ${item.is_test ? "test" : ""}">${label}</span>
          <span class="subject">${item.subject}</span>
          ${item.lesson_hour !== null
            ? html`<span class="meta">${format(texts.lesson_hour, { n: item.lesson_hour })}</span>`
            : nothing}
          ${item.cancelled ? html`<span class="badge">${texts.cancelled}</span>` : nothing}
          ${item.has_attachments
            ? html`<span class="meta attachments" title=${texts.attachments}
                ><svg viewBox="0 0 24 24" aria-hidden="true"><path d=${PAPERCLIP}></path></svg
                ><span class="sr-only">${texts.attachments}</span></span
              >`
            : nothing}
        </div>
        ${item.text
          ? html`<button
              type="button"
              class="text ${expanded ? "expanded" : ""}"
              aria-expanded=${expanded ? "true" : "false"}
              title=${expanded ? texts.collapse : texts.expand}
              @click=${() => {
                this._toggleExpanded(item.uid);
              }}
            >${item.text}</button>`
          : nothing}
        ${this._renderProgress(item, texts, enabled)}
      </div>
    </li>`;
  }

  private _renderProgress(item: HomeworkItem, texts: Texts, enabled: boolean): TemplateResult {
    // A stored value between the steps (say 40 %) leaves every radio unchecked; the
    // nearest step takes the tab stop and the tint.
    const nearest = snapToStep(item.progress);
    const exact = (STEPS as readonly number[]).includes(item.progress);
    return html`<div class="progress">
      <div
        class="segments"
        role="radiogroup"
        aria-label=${format(texts.progress_of, { subject: item.subject })}
      >
        ${STEPS.map(
          (step) => html`<button
            type="button"
            role="radio"
            class="segment ${step === nearest ? "selected" : ""} ${step < nearest ? "below" : ""} ${exact ? "" : "between"}"
            aria-checked=${exact && step === nearest ? "true" : "false"}
            aria-label=${format(texts.percent, { n: step })}
            tabindex=${step === nearest ? 0 : -1}
            ?disabled=${!enabled}
            @click=${() => {
              if (step !== item.progress) void this._setProgress(item.uid, step);
            }}
            @keydown=${(event: KeyboardEvent) => {
              this._onSegmentKey(event, item.uid, item.progress);
            }}
          >
            ${step}
          </button>`,
        )}
      </div>
      <span class="percent">${format(texts.percent, { n: item.progress })}</span>
    </div>`;
  }

  private _onSegmentKey(event: KeyboardEvent, uid: string, progress: number): void {
    const index = STEPS.indexOf(snapToStep(progress) as (typeof STEPS)[number]);
    let next: number;
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        next = Math.min(index + 1, STEPS.length - 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        next = Math.max(index - 1, 0);
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = STEPS.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    const target = STEPS[next];
    if (target === undefined || target === progress) return;
    const group = event.currentTarget as HTMLElement;
    void this._setProgress(uid, target);
    void this.updateComplete.then(() => {
      group.parentElement?.querySelector<HTMLElement>('[tabindex="0"]')?.focus();
    });
  }

  static override styles = css`
    :host {
      display: block;
    }
    ha-card {
      display: block;
      overflow: hidden;
    }
    .content {
      padding: 0 16px 16px;
    }
    .content:not(.titled) {
      padding-top: 12px;
    }
    .state {
      margin: 16px 0;
      text-align: center;
      color: var(--secondary-text-color);
    }
    .state.error {
      color: var(--error-color);
    }
    .state.empty {
      font-size: 1.1em;
      padding: 12px 0;
    }
    .banner {
      margin: 0 0 12px;
      padding: 8px 12px;
      border-radius: 8px;
      background: color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent);
      color: var(--primary-text-color);
      font-size: 0.9em;
    }
    .bars {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0 0 12px;
    }
    .titled .bars {
      margin-top: 12px;
    }
    .bar-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 0.9em;
      font-weight: 500;
      color: var(--primary-text-color);
    }
    .bar-value {
      font-variant-numeric: tabular-nums;
    }
    .track {
      height: 8px;
      margin: 4px 0 2px;
      border-radius: 4px;
      overflow: hidden;
      background: var(--divider-color);
    }
    .fill {
      height: 100%;
      border-radius: 4px;
      background: var(--primary-color);
    }
    .bar-note {
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .bar.unavailable .bar-head {
      color: var(--secondary-text-color);
    }
    .days.stale {
      opacity: 0.55;
    }
    h3.section {
      margin: 16px 0 0;
      font-size: 0.85em;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--secondary-text-color);
    }
    h4 {
      margin: 16px 0 4px;
      font-size: 1em;
      font-weight: 600;
      color: var(--primary-text-color);
    }
    h4::first-letter {
      text-transform: uppercase;
    }
    h4.today {
      color: var(--primary-color);
    }
    ul {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .item {
      display: flex;
      gap: 12px;
      padding: 10px 0 10px 8px;
      border-top: 1px solid var(--divider-color);
      border-left: 3px solid transparent;
    }
    .item:first-child {
      border-top: none;
    }
    .item.test {
      border-left-color: var(--warning-color, #ffa600);
      background: color-mix(in srgb, var(--warning-color, #ffa600) 8%, transparent);
    }
    .item.done .subject,
    .item.done .text {
      color: var(--secondary-text-color);
      text-decoration: line-through;
    }
    input[type="checkbox"] {
      flex: none;
      width: 22px;
      height: 22px;
      margin: 2px 0 0;
      accent-color: var(--primary-color);
      cursor: pointer;
    }
    input[type="checkbox"]:disabled {
      cursor: default;
    }
    .main {
      flex: 1;
      min-width: 0;
    }
    .head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px 8px;
    }
    .subject {
      font-weight: 500;
      color: var(--primary-text-color);
      overflow-wrap: anywhere;
    }
    .item.test .subject {
      font-weight: 700;
    }
    .chip {
      padding: 1px 8px;
      border-radius: 10px;
      font-size: 0.75em;
      font-weight: 500;
      background: var(--secondary-background-color);
      color: var(--secondary-text-color);
      border: 1px solid var(--divider-color);
    }
    .chip.test {
      font-weight: 700;
      color: var(--text-primary-color, #fff);
      background: var(--warning-color, #ffa600);
      border-color: var(--warning-color, #ffa600);
    }
    .meta {
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .attachments svg {
      width: 16px;
      height: 16px;
      vertical-align: middle;
      fill: currentColor;
    }
    .badge {
      padding: 1px 8px;
      border-radius: 10px;
      font-size: 0.75em;
      font-weight: 500;
      color: var(--error-color);
      border: 1px solid var(--error-color);
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }
    .text {
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 2;
      line-clamp: 2;
      overflow: hidden;
      width: 100%;
      margin: 4px 0 0;
      padding: 0;
      border: none;
      background: none;
      font: inherit;
      font-size: 0.9em;
      text-align: left;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--secondary-text-color);
      cursor: pointer;
    }
    .text.expanded {
      display: block;
      -webkit-line-clamp: unset;
      line-clamp: unset;
      overflow: visible;
    }
    .progress {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 8px;
    }
    .segments {
      display: flex;
      flex: 0 1 260px;
      min-width: 0;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      overflow: hidden;
    }
    .segment {
      flex: 1;
      min-width: 0;
      min-height: 36px;
      padding: 0;
      border: none;
      border-left: 1px solid var(--divider-color);
      background: transparent;
      color: var(--secondary-text-color);
      font: inherit;
      font-size: 0.8em;
      cursor: pointer;
    }
    .segment:first-child {
      border-left: none;
    }
    .segment.below {
      background: color-mix(in srgb, var(--primary-color) 22%, transparent);
    }
    .segment.between.selected {
      background: color-mix(in srgb, var(--primary-color) 55%, transparent);
    }
    .segment.selected {
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
      font-weight: 700;
    }
    .segment:disabled {
      cursor: default;
    }
    .segment:focus-visible,
    .text:focus-visible,
    input[type="checkbox"]:focus-visible,
    .toast button:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    .percent {
      font-size: 0.8em;
      min-width: 3.2em;
      color: var(--secondary-text-color);
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
    @media (max-width: 480px) {
      .segments {
        flex: 1 1 auto;
      }
      .segment {
        min-height: 40px;
      }
    }
  `;
}
