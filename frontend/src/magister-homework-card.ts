import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import {
  STEPS,
  applyLabelRemovals,
  applyOverlay,
  applyOverrides,
  applyProposalOverlay,
  applySubtaskEdits,
  dateBounds,
  dayMaximum,
  formatDay,
  formatMinutes,
  formatMinutesShort,
  addDays,
  formatRange,
  formatShortDay,
  groupEntries,
  isDerived,
  isOpenProposal,
  hasOverrideFields,
  labelKey,
  loadSwitches,
  menuActions,
  minuteChoices,
  PROGRESS_PERIODS,
  barPercent,
  normalizeConfig,
  optimisticOverlay,
  optimisticOverride,
  overrideFieldsOf,
  parentUid,
  plannedMinutes,
  proposedMaximum,
  reflectsEdit,
  saveSwitches,
  snapToStep,
  storageKey,
  todayIso,
  toggleTarget,
  type Entry,
  type EntryGroup,
  type NormalizedConfig,
  type OverrideChange,
  type OverrideFields,
  type Overlay,
  type ProposalAnswer,
  type SubtaskEdit,
} from "./logic";
import { HomeworkSubscription, type LoadError } from "./subscription";
import { effectiveLabel } from "./timer";
import { TimerController } from "./timer-controller";
import {
  renderActions,
  renderCountdown,
  renderLive,
  renderPanel,
  renderReplaceConfirm,
  renderSettings,
  renderSettingsButton,
  renderStartButton,
  timerStyles,
  type TimerContext,
} from "./timer-views";
import "./label-dialog";
import {
  TRANSLATIONS,
  effectiveLanguage,
  format,
  typeLabel,
  type Language,
  type Texts,
} from "./translations";
import type {
  CardConfig,
  Hass,
  HomeworkItem,
  HomeworkPayload,
  ManualLabel,
  Proposal,
  RespondResult,
  SetOverrideResult,
  SetProgressResult,
  Subtask,
  SubtaskResult,
  WsError,
} from "./types";

const SET_PROGRESS = "magister/homework/set_progress";
const REMOVE_LABEL = "magister/homework/remove_label";
const SET_OVERRIDE = "magister/homework/set_override";
const ADD_SUBTASK = "magister/homework/add_subtask";
const UPDATE_SUBTASK = "magister/homework/update_subtask";
const DELETE_SUBTASK = "magister/homework/delete_subtask";
const RESPOND_PROPOSAL = "magister/homework/respond_proposal";
const MAX_TITLE = 100;
const TOAST_MS = 6000;

/** The inline form to add a subtask to an item, or to edit one. */
interface SubForm {
  mode: "add" | "edit";
  itemUid: string;
  /** Edit only. */
  subUid?: string;
  title: string;
  date: string;
  /** The estimated time; null when unknown (none chosen). */
  minutes: number | null;
  /** Edit only: the stored estimate, which stays selectable after it is changed. */
  storedMinutes?: number | null;
  error: string;
  busy: boolean;
}

const PAPERCLIP =
  "M16.5,6V17.5A4,4 0 0,1 12.5,21.5A4,4 0 0,1 8.5,17.5V5A2.5,2.5 0 0,1 11,2.5A2.5,2.5 0 0,1 13.5,5V15.5A1,1 0 0,1 12.5,16.5A1,1 0 0,1 11.5,15.5V6H10V15.5A2.5,2.5 0 0,0 12.5,18A2.5,2.5 0 0,0 15,15.5V5A4,4 0 0,0 11,1A4,4 0 0,0 7,5V17.5A5.5,5.5 0 0,0 12.5,23A5.5,5.5 0 0,0 18,17.5V6H16.5Z";

/** A list with an indented second level (mdi-subdirectory-arrow-right), for the subtask marker. */
const SUBTASKS_ICON = "M19,15L13,21L11.58,19.58L15.17,16H4V4H6V14H15.17L11.58,10.42L13,9L19,15Z";

export class MagisterHomeworkCard extends LitElement {
  static override properties = {
    _payload: { state: true },
    _loadError: { state: true },
    _offline: { state: true },
    _overlay: { state: true },
    _expanded: { state: true },
    _toast: { state: true },
    _showCompleted: { state: true },
    _showPast: { state: true },
    _hiddenLabels: { state: true },
    _confirm: { state: true },
    _dialogOpen: { state: true },
    _overrideOverlay: { state: true },
    _menu: { state: true },
    _subEdits: { state: true },
    _form: { state: true },
    _subConfirm: { state: true },
    _proposalOverlay: { state: true },
    _proposalConfirm: { state: true },
  };

  declare _payload: HomeworkPayload | undefined;
  declare _loadError: LoadError | undefined;
  declare _offline: boolean;
  declare _overlay: ReadonlyMap<string, Overlay>;
  declare _expanded: ReadonlySet<string>;
  declare _toast: string;
  declare _showCompleted: boolean;
  declare _showPast: boolean;
  /** Manual labels being removed (hidden at once; shown again if the removal fails). */
  declare _hiddenLabels: ReadonlySet<string>;
  /** The manual label waiting for its remove confirmation. */
  declare _confirm: { uid: string; label: ManualLabel } | undefined;
  declare _dialogOpen: boolean;
  /** Optimistic overrides of the Magister label, until the backend has answered. */
  declare _overrideOverlay: ReadonlyMap<string, OverrideFields>;
  /** The uid of the item whose Magister-label menu is open. */
  declare _menu: string | undefined;
  /** Optimistic subtask edits and deletions, until the backend has answered. */
  declare _subEdits: ReadonlyMap<string, SubtaskEdit>;
  declare _form: SubForm | undefined;
  /** The uid of the subtask waiting for its delete confirmation. */
  declare _subConfirm: string | undefined;
  /** Optimistic answers to proposals, until the backend has answered. */
  declare _proposalOverlay: ReadonlyMap<string, ProposalAnswer>;
  /** The id of the proposal waiting for its accept confirmation. */
  declare _proposalConfirm: string | undefined;

  private _storageKey = "";
  private readonly _removing = new Set<string>();

  private _config: NormalizedConfig | undefined;
  private _hass: Hass | undefined;
  private readonly _subscription: HomeworkSubscription;
  private readonly _timer: TimerController;
  /** The request that last changed an item: only its outcome touches the view. */
  private readonly _tokens = new Map<string, number>();
  private readonly _overrideTokens = new Map<string, number>();
  private readonly _subTokens = new Map<string, number>();
  private readonly _proposalTokens = new Map<string, number>();
  /** A subtask row that should take the focus as soon as it is rendered (after an add). */
  private _pendingFocus: string | undefined;
  /** The inline form should focus its title field when it renders. */
  private _focusForm = false;
  private _nextToken = 0;
  private _hassKey = "";
  private _dayTimer: ReturnType<typeof setInterval> | undefined;
  private _shownDay = "";
  /** Items ticked off in this view: they stay visible until the card is reloaded. */
  private readonly _touched = new Set<string>();
  private _toastTimer: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    super();
    this._subscription = new HomeworkSubscription({
      isConnected: () => this.isConnected,
      hass: () => this._hass,
      entity: () => this._config?.entity,
      onPayload: (payload) => {
        this._onPayload(payload);
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
      itemLabel: (item) => this._itemLabel(item, this._texts()),
      fallbackFocus: () => [".toolbar .switch"],
      beginProgress: (uid, progress) => this._beginProgress(uid, progress),
    });
    this._offline = false;
    this._overlay = new Map();
    this._expanded = new Set();
    this._toast = "";
    this._showCompleted = false;
    this._showPast = false;
    this._hiddenLabels = new Set();
    this._confirm = undefined;
    this._dialogOpen = false;
    this._overrideOverlay = new Map();
    this._menu = undefined;
    this._subEdits = new Map();
    this._form = undefined;
    this._subConfirm = undefined;
    this._proposalOverlay = new Map();
    this._proposalConfirm = undefined;
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
      this._subscription.reset();
      this._payload = undefined;
      this._loadError = undefined;
      this._offline = false;
      this._overlay = new Map();
      this._expanded = new Set();
      this._tokens.clear();
      this._touched.clear();
      this._hiddenLabels = new Set();
      this._removing.clear();
      this._confirm = undefined;
      this._dialogOpen = false;
      this._overrideOverlay = new Map();
      this._overrideTokens.clear();
      this._subEdits = new Map();
      this._subTokens.clear();
      this._proposalOverlay = new Map();
      this._proposalTokens.clear();
      this._proposalConfirm = undefined;
      this._form = undefined;
      this._subConfirm = undefined;
      this._pendingFocus = undefined;
      this._timer.reset();
      this._closeMenu(false);
      this._subscription.resetBackoff();
    }
    this._config = next;
    // The remembered switches of this card; a changed config has another key and so starts over.
    this._storageKey = storageKey(next);
    const remembered = loadSwitches(this._storageKey);
    this._showCompleted = remembered?.show_completed ?? next.show_completed;
    this._showPast = remembered?.show_past ?? next.show_past;
    this.requestUpdate();
    this._subscription.ensure();
  }

  set hass(hass: Hass | undefined) {
    this._hass = hass;
    // Home Assistant sets hass on every state change: render only when it matters.
    const key = `${hass?.locale?.language ?? ""}|${hass?.language ?? ""}|${hass?.config?.time_zone ?? ""}`;
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
    const items = this._visibleItems().length;
    return items === 0 ? 3 : 2 + items * 2;
  }

  getGridOptions(): Record<string, number> {
    return { columns: 12, min_columns: 6, min_rows: 3 };
  }

  // -- lifecycle --

  override connectedCallback(): void {
    super.connectedCallback();
    this._subscription.ensure();
    this._timer.connected();
    // Re-render when the day changes while the dashboard stays open.
    this._dayTimer = setInterval(() => {
      if (this._currentDay() !== this._shownDay) this.requestUpdate();
    }, 60_000);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._subscription.reset();
    this._timer.disconnected();
    if (this._toastTimer) clearTimeout(this._toastTimer);
    if (this._dayTimer) clearInterval(this._dayTimer);
    this._dayTimer = undefined;
    this._closeMenu(false);
  }

  // -- subscription --

  private _onPayload(payload: HomeworkPayload): void {
    this._payload = payload;
    this._loadError = undefined;
    this._offline = false;
    // Confirmed overlays are replaced by the pushed state; requests still in flight stay.
    const kept = new Map<string, Overlay>();
    for (const [uid, overlay] of this._overlay) {
      if (this._tokens.has(uid)) kept.set(uid, overlay);
    }
    this._overlay = kept;
    const keptOverrides = new Map<string, OverrideFields>();
    for (const [uid, fields] of this._overrideOverlay) {
      if (this._overrideTokens.has(uid)) keptOverrides.set(uid, fields);
    }
    this._overrideOverlay = keptOverrides;
    const keptEdits = new Map<string, SubtaskEdit>();
    for (const [uid, edit] of this._subEdits) {
      if (this._subTokens.has(uid)) keptEdits.set(uid, edit);
    }
    this._subEdits = keptEdits;
    const keptAnswers = new Map<string, ProposalAnswer>();
    for (const [id, answer] of this._proposalOverlay) {
      if (this._proposalTokens.has(id)) keptAnswers.set(id, answer);
    }
    this._proposalOverlay = keptAnswers;
    // Removals that were confirmed are in the pushed state; those in flight stay hidden.
    this._hiddenLabels = new Set([...this._hiddenLabels].filter((key) => this._removing.has(key)));
    this._timer.onPayload();
  }

  /** The optimistic progress of a timer stop with progress, or "Klaar"; the function settles it. */
  private _beginProgress(uid: string, progress: number): (ok: boolean) => void {
    const source = this._findTarget(uid);
    if (!source) return () => undefined;
    const token = ++this._nextToken;
    this._tokens.set(uid, token);
    if (progress >= 100) {
      this._touched.add(uid);
      this._touched.add(parentUid(uid));
    }
    const shown = { ...source, ...this._overlay.get(uid) };
    this._overlay = new Map(this._overlay).set(uid, optimisticOverlay(shown, progress));
    return (ok) => {
      if (this._tokens.get(uid) !== token) return;
      this._tokens.delete(uid);
      const next = new Map(this._overlay);
      // Accepted: the push replaces the overlay (at once when it already shows the value).
      if (!ok || this._findTarget(uid)?.progress === progress) next.delete(uid);
      this._overlay = next;
    };
  }

  // -- progress --

  private async _setProgress(uid: string, progress: number): Promise<void> {
    const hass = this._hass;
    const entity = this._config?.entity;
    const source = this._findTarget(uid);
    if (!hass || !entity || !source || !this._payload?.available || this._offline) return;
    const token = ++this._nextToken;
    this._tokens.set(uid, token);
    if (progress >= 100) {
      this._touched.add(uid);
      // A ticked subtask keeps its item visible too, so neither vanishes under the finger.
      this._touched.add(parentUid(uid));
    }
    const shown = { ...source, ...this._overlay.get(uid) };
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
      const current = this._findTarget(uid);
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
      this._showToast(
        code === "unauthorized"
          ? texts.save_unauthorized
          : code === "item_disabled"
            ? (texts.label_errors.item_disabled ?? texts.save_failed)
            : code === "item_has_subtasks" || (code === "item_not_found" && uid.includes(":sub:"))
              ? (texts.sub.errors[code] ?? texts.save_failed)
              : texts.save_failed,
      );
    }
  }

  /** An item or a subtask of the pushed state (without optimistic changes). */
  private _findTarget(uid: string): Pick<HomeworkItem, "uid" | "progress" | "completed" | "last_partial"> | undefined {
    for (const item of this._payload?.items ?? []) {
      if (item.uid === uid) return item;
      const subtask = item.subtasks?.find((candidate) => candidate.uid === uid);
      if (subtask) return subtask;
    }
    return undefined;
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

  // -- Magister label menu and overrides --

  private _menuButton(uid: string): HTMLElement | null {
    return (
      this.shadowRoot?.querySelector<HTMLElement>(`[data-menu-button="${CSS.escape(uid)}"]`) ?? null
    );
  }

  private _menuItems(): HTMLElement[] {
    return [...(this.shadowRoot?.querySelectorAll<HTMLElement>('.menu [role="menuitem"]') ?? [])];
  }

  private readonly _onOutsideClick = (event: Event): void => {
    const uid = this._menu;
    if (uid === undefined) return;
    const path = event.composedPath();
    const menu = this.shadowRoot?.querySelector(".menu");
    if ((menu && path.includes(menu)) || path.includes(this._menuButton(uid) as EventTarget)) return;
    this._closeMenu(false);
  };

  private _openMenu(uid: string, where: "first" | "last"): void {
    this._menu = uid;
    document.addEventListener("click", this._onOutsideClick, true);
    void this.updateComplete.then(() => {
      const items = this._menuItems();
      (where === "first" ? items[0] : items[items.length - 1])?.focus();
    });
  }

  /** Close the menu; with `returnFocus` the focus goes back to the chip that opened it. */
  private _closeMenu(returnFocus: boolean): void {
    const uid = this._menu;
    document.removeEventListener("click", this._onOutsideClick, true);
    if (uid === undefined) return;
    this._menu = undefined;
    if (returnFocus) {
      void this.updateComplete.then(() => {
        this._menuButton(uid)?.focus();
      });
    }
  }

  private _onChipKey(event: KeyboardEvent, uid: string): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      this._openMenu(uid, "first");
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      this._openMenu(uid, "last");
    } else if (event.key === "Escape" && this._menu === uid) {
      event.preventDefault();
      this._closeMenu(true);
    }
  }

  private _onMenuKey(event: KeyboardEvent, uid: string): void {
    const items = this._menuItems();
    const index = items.indexOf(event.target as HTMLElement);
    let next: number;
    switch (event.key) {
      case "ArrowDown":
        next = (index + 1) % items.length;
        break;
      case "ArrowUp":
        next = (index - 1 + items.length) % items.length;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = items.length - 1;
        break;
      case "Escape":
        event.preventDefault();
        event.stopPropagation();
        this._closeMenu(true);
        return;
      case "Tab":
        // Leave the menu: the focus moves on from the chip, not from a vanished item.
        this._menuButton(uid)?.focus();
        this._closeMenu(false);
        return;
      default:
        return;
    }
    event.preventDefault();
    items[next]?.focus();
  }

  private _choose(item: HomeworkItem, change: OverrideChange): void {
    this._closeMenu(true);
    void this._setOverride(item, change);
  }

  private async _setOverride(item: HomeworkItem, change: OverrideChange): Promise<void> {
    const hass = this._hass;
    const entity = this._config?.entity;
    const uid = item.uid;
    if (!hass || !entity || !this._payload?.available || this._offline) return;
    const token = ++this._nextToken;
    this._overrideTokens.set(uid, token);
    // A disabled item is completed: it stays on screen for this session so it can be restored.
    if (change.mode === "disable") this._touched.add(uid);
    const shown = this._items().find((candidate) => candidate.uid === uid) ?? item;
    this._overrideOverlay = new Map(this._overrideOverlay).set(
      uid,
      optimisticOverride(shown, change),
    );
    try {
      const result = await hass.callWS<SetOverrideResult>({
        type: SET_OVERRIDE,
        entity_id: entity,
        appointment: uid,
        mode: change.mode,
        ...(change.mode === "replace" ? { label: change.label.id } : {}),
      });
      if (this._overrideTokens.get(uid) !== token) return;
      this._overrideTokens.delete(uid);
      const next = new Map(this._overrideOverlay);
      const current = this._payload.items.find((candidate) => candidate.uid === uid);
      // The push usually arrives first; otherwise keep the confirmed state until it does.
      // No item in the answer: nothing to keep.
      const confirmed = result.item ? overrideFieldsOf(result.item) : undefined;
      if (!confirmed || (current && hasOverrideFields(current, confirmed))) next.delete(uid);
      else next.set(uid, confirmed);
      this._overrideOverlay = next;
    } catch (error) {
      if (this._overrideTokens.get(uid) !== token) return;
      this._overrideTokens.delete(uid);
      const next = new Map(this._overrideOverlay);
      next.delete(uid);
      this._overrideOverlay = next;
      const code = (error as WsError | undefined)?.code;
      const texts = this._texts();
      this._showToast((code ? texts.label_errors[code] : undefined) ?? texts.save_failed);
    }
  }

  // -- proposals --

  /** The proposals of the payload with the optimistic answers applied. */
  private _proposals(): Proposal[] {
    return applyProposalOverlay(this._payload?.proposals ?? [], this._proposalOverlay);
  }

  private _proposalSummary(proposal: Proposal, texts: Texts): string {
    const lang = this._language() === "nl" ? "nl" : "en";
    if (proposal.kind === "weekdays") {
      const values = (proposal.weekdays ?? [])
        .map(
          (minutes, index) =>
            `${texts.proposal.weekdays_short[index] ?? ""} ${minutes === 0 ? texts.proposal.none : formatMinutesShort(minutes, lang)}`,
        )
        .join(", ");
      return format(texts.proposal.weekdays, { reason: proposal.reason, values });
    }
    return format(texts.proposal.period, {
      reason: proposal.reason,
      range: formatRange(proposal.start ?? "", proposal.end ?? "", lang === "nl" ? "nl" : "en-GB"),
      max: formatMinutes(proposal.minutes ?? 0, lang),
    });
  }

  /** The summary with the date range kept on one line. */
  private _proposalSummaryHtml(proposal: Proposal, texts: Texts): TemplateResult | string {
    if (proposal.kind === "weekdays") return this._proposalSummary(proposal, texts);
    const lang = this._language() === "nl" ? "nl" : "en";
    const marker = "\u0000";
    const range = formatRange(proposal.start ?? "", proposal.end ?? "", lang === "nl" ? "nl" : "en-GB");
    const parts = format(texts.proposal.period, {
      reason: proposal.reason,
      range: marker,
      max: formatMinutes(proposal.minutes ?? 0, lang),
    }).split(marker);
    if (parts.length !== 2) return this._proposalSummary(proposal, texts);
    return html`${parts[0]}<span class="nowrap">${range}</span>${parts[1]}`;
  }

  /** A period proposal can be answered until the day before it starts; a weekdays proposal expires on a date. */
  private _expiryText(proposal: Proposal, texts: Texts, lang: string): string {
    if (proposal.kind === "period") {
      return format(texts.proposal.answer_by, { date: formatShortDay(addDays(proposal.expires, -1), lang) });
    }
    return format(texts.proposal.expires, { date: formatShortDay(proposal.expires, lang) });
  }

  private _askAccept(id: string): void {
    this._toast = "";
    this._proposalConfirm = id;
    void this.updateComplete.then(() => {
      this.shadowRoot?.querySelector<HTMLElement>(".proposal .confirm .cancel")?.focus();
    });
  }

  private _cancelAccept(id: string): void {
    this._proposalConfirm = undefined;
    void this.updateComplete.then(() => {
      this.shadowRoot
        ?.querySelector<HTMLElement>(`[data-accept="${CSS.escape(id)}"]`)
        ?.focus();
    });
  }

  private async _respond(proposal: Proposal, answer: "accept" | "reject"): Promise<void> {
    const hass = this._hass;
    const entity = this._config?.entity;
    this._proposalConfirm = undefined;
    if (!hass || !entity || !this._payload?.available || this._offline) return;
    const id = proposal.id;
    const token = ++this._nextToken;
    this._proposalTokens.set(id, token);
    // The block is gone once it is answered: focus moves on to the next proposal, else the switches.
    const others = this._proposals().filter((other) => isOpenProposal(other) && other.id !== id);
    this._proposalOverlay = new Map(this._proposalOverlay).set(id, {
      status: answer === "accept" ? "accepted" : "rejected",
      closed: this._currentDay(),
    });
    this._focusAfter([
      ...others.map((other) => `[data-proposal="${CSS.escape(other.id)}"] button`),
      ".toolbar .switch",
    ]);
    const texts = this._texts();
    try {
      const result = await hass.callWS<RespondResult>({
        type: RESPOND_PROPOSAL,
        entity_id: entity,
        proposal: id,
        answer,
      });
      if (this._proposalTokens.get(id) !== token) return;
      this._proposalTokens.delete(id);
      const next = new Map(this._proposalOverlay);
      const current = this._payload.proposals?.find((candidate) => candidate.id === id);
      // The push usually arrives first; otherwise keep the confirmed answer until it does.
      if (current && current.status !== "proposed") next.delete(id);
      else {
        next.set(id, {
          status: result.proposal.status,
          closed: result.proposal.closed,
          answered_by: result.proposal.answered_by,
        });
      }
      this._proposalOverlay = next;
      this._showToast(answer === "accept" ? texts.proposal.accepted_toast : texts.proposal.rejected_toast);
    } catch (error) {
      if (this._proposalTokens.get(id) !== token) return;
      this._proposalTokens.delete(id);
      const next = new Map(this._proposalOverlay);
      next.delete(id);
      this._proposalOverlay = next;
      const code = (error as WsError | undefined)?.code;
      this._showToast(
        (code ? texts.proposal.errors[code] : undefined) ?? texts.proposal.errors.default ?? texts.save_failed,
      );
      this._focusAfter([`[data-proposal="${CSS.escape(id)}"] button`]);
    }
  }

  private _renderProposals(texts: Texts, enabled: boolean): TemplateResult | typeof nothing {
    const open = this._proposals().filter(isOpenProposal);
    if (open.length === 0) return nothing;
    const lang = this._language() === "nl" ? "nl" : "en-GB";
    return html`<div class="proposals">
      ${open.map((proposal) => {
        const summary = this._proposalSummary(proposal, texts);
        const confirming = this._proposalConfirm === proposal.id;
        return html`<section
          class="proposal"
          role="group"
          data-proposal=${proposal.id}
          aria-label=${format(texts.proposal.group_aria, { summary })}
        >
          <p class="proposal-text">
            <span class="proposal-title">${texts.proposal.title}:</span> ${this._proposalSummaryHtml(proposal, texts)}
            <span class="proposal-expires">${this._expiryText(proposal, texts, lang)}</span>
          </p>
          ${confirming
            ? html`<div
                class="confirm"
                role="group"
                aria-label=${texts.proposal.confirm}
                @keydown=${(event: KeyboardEvent) => {
                  if (event.key === "Escape") {
                    event.stopPropagation();
                    this._cancelAccept(proposal.id);
                  }
                }}
              >
                <span>${texts.proposal.confirm}</span>
                <button type="button" class="cancel" @click=${() => {
                  this._cancelAccept(proposal.id);
                }}>${texts.proposal.confirm_no}</button>
                <button type="button" class="primary" ?disabled=${!enabled} @click=${() => {
                  void this._respond(proposal, "accept");
                }}>${texts.proposal.confirm_yes}</button>
              </div>`
            : html`<div class="proposal-actions">
                <button
                  type="button"
                  class="primary"
                  data-accept=${proposal.id}
                  ?disabled=${!enabled}
                  aria-label=${format(texts.proposal.accept_aria, { summary })}
                  @click=${() => {
                    this._askAccept(proposal.id);
                  }}
                >${texts.proposal.accept}</button>
                <button
                  type="button"
                  class="reject"
                  data-reject=${proposal.id}
                  ?disabled=${!enabled}
                  aria-label=${format(texts.proposal.reject_aria, { summary })}
                  @click=${() => {
                    void this._respond(proposal, "reject");
                  }}
                >${texts.proposal.reject}</button>
              </div>`}
        </section>`;
      })}
    </div>`;
  }

  /** The answered and expired proposals, under the "Eerder" switch. */
  private _renderClosedProposals(texts: Texts): TemplateResult | typeof nothing {
    if (!this._showPast) return nothing;
    const closed = this._proposals().filter((proposal) => !isOpenProposal(proposal));
    if (closed.length === 0) return nothing;
    const lang = this._language() === "nl" ? "nl" : "en-GB";
    return html`<section class="closed-proposals" aria-labelledby="closed-proposals-title">
      <h3 class="section" id="closed-proposals-title">${texts.proposal.earlier}</h3>
      <ul>
        ${closed.map((proposal) => {
          const status = texts.proposal[proposal.status as "accepted" | "rejected" | "expired"];
          const behalf =
            proposal.answered_by === "on_behalf" ? ` ${texts.proposal.on_behalf}` : "";
          const when = proposal.closed
            ? format(texts.proposal.closed_on, {
                status: `${status}${behalf}`,
                date: formatShortDay(proposal.closed, lang),
              })
            : `${status}${behalf}`;
          return html`<li class="closed-proposal" data-proposal=${proposal.id}>
            <span class="proposal-status ${proposal.status}">${when}</span>
            <span>${this._proposalSummaryHtml(proposal, texts)}</span>
          </li>`;
        })}
      </ul>
    </section>`;
  }

  // -- manual labels --

  private _askRemove(uid: string, label: ManualLabel): void {
    this._confirm = { uid, label };
    void this.updateComplete.then(() => {
      this.shadowRoot?.querySelector<HTMLElement>(".confirm .cancel")?.focus();
    });
  }

  private _cancelRemove(): void {
    const confirm = this._confirm;
    this._confirm = undefined;
    if (!confirm) return;
    void this.updateComplete.then(() => {
      this.shadowRoot
        ?.querySelector<HTMLElement>(`[data-key="${CSS.escape(labelKey(confirm.uid, confirm.label.id))}"]`)
        ?.focus();
    });
  }

  private async _removeLabel(uid: string, label: ManualLabel): Promise<void> {
    const hass = this._hass;
    const entity = this._config?.entity;
    this._confirm = undefined;
    if (!hass || !entity) return;
    const key = labelKey(uid, label.id);
    this._removing.add(key);
    this._hiddenLabels = new Set(this._hiddenLabels).add(key);
    // The focused × or confirm button is gone now: the next chip, else the item's
    // checkbox, else the + button.
    void this.updateComplete.then(() => {
      const row = this.shadowRoot?.querySelector(`li[data-uid="${CSS.escape(uid)}"]`);
      const target =
        row?.querySelector<HTMLElement>(".chip-remove:not(:disabled)") ??
        row?.querySelector<HTMLElement>('input[type="checkbox"]') ??
        this.shadowRoot?.querySelector<HTMLElement>(".add");
      target?.focus();
    });
    try {
      await hass.callWS({ type: REMOVE_LABEL, entity_id: entity, appointment: uid, label: label.id });
      this._removing.delete(key);
    } catch (error) {
      this._removing.delete(key);
      const code = (error as WsError | undefined)?.code;
      // The label is already gone from the lesson: that is what was asked for.
      if (code === "label_not_on_appointment") return;
      const next = new Set(this._hiddenLabels);
      next.delete(key);
      this._hiddenLabels = next;
      const texts = this._texts();
      this._showToast(
        (code ? texts.label_errors[code] : undefined) ?? texts.save_failed,
      );
    }
  }

  private _closeDialog = (): void => {
    this._dialogOpen = false;
    void this.updateComplete.then(() => {
      this.shadowRoot?.querySelector<HTMLElement>(".add")?.focus();
    });
  };

  // -- view model --

  /** The card's language: the `language` option, or the Home Assistant language. */
  private _language(): Language {
    return effectiveLanguage(
      this._config?.language,
      this._hass?.locale?.language ?? this._hass?.language,
    );
  }

  private _texts(): Texts {
    return TRANSLATIONS[this._language()];
  }

  private _items(): HomeworkItem[] {
    if (!this._payload) return [];
    return applyLabelRemovals(
      applyOverrides(
        applyOverlay(
          applySubtaskEdits(this._payload.items, this._subEdits, this._currentDay()),
          this._overlay,
        ),
        this._overrideOverlay,
      ),
      this._hiddenLabels,
    );
  }

  private _setSwitch(name: "show_completed" | "show_past", value: boolean): void {
    if (name === "show_completed") this._showCompleted = value;
    else this._showPast = value;
    saveSwitches(this._storageKey, {
      show_completed: this._showCompleted,
      show_past: this._showPast,
    });
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

  private _visibleGroups(): EntryGroup[] {
    const config = this._config;
    if (!config || !this._payload) return [];
    return groupEntries(this._items(), {
      showCompleted: this._showCompleted,
      showPast: this._showPast,
      daysAhead: config.days_ahead,
      today: this._today(),
      keep: this._touched,
    });
  }

  private _visibleItems(): Entry[] {
    return this._visibleGroups().flatMap((group) => group.entries);
  }

  private _dayTitle(group: Pick<EntryGroup, "kind" | "date">, texts: Texts): string {
    if (group.kind === "overdue") return texts.sub.overdue_group;
    if (group.kind === "today") return texts.today;
    if (group.kind === "tomorrow") return texts.tomorrow;
    return formatDay(group.date, this._language() === "nl" ? "nl" : "en-GB");
  }

  // -- rendering --

  protected override willUpdate(): void {
    this._timer.willUpdate();
    // A removal can no longer be confirmed while the card is read-only.
    if (this._confirm && (this._offline || this._payload?.available !== true)) {
      this._confirm = undefined;
    }
    // Subtask forms and confirmations go when the card turns read-only or their target is gone.
    const readOnly = this._offline || this._payload?.available !== true;
    if (this._form && (readOnly || !this._formTarget(this._form))) this._form = undefined;
    if (this._subConfirm && (readOnly || !this._findSubtask(this._subConfirm))) {
      this._subConfirm = undefined;
    }
    const confirming = this._proposalConfirm;
    if (
      confirming !== undefined &&
      (readOnly || !this._proposals().some((p) => p.id === confirming && isOpenProposal(p)))
    ) {
      this._proposalConfirm = undefined;
    }
    // The menu goes when the card turns read-only or its item is gone.
    if (
      this._menu !== undefined &&
      (this._offline ||
        this._payload?.available !== true ||
        !this._payload.items.some((item) => item.uid === this._menu))
    ) {
      this._closeMenu(false);
    }
  }

  protected override render(): TemplateResult {
    const config = this._config;
    const texts = this._texts();
    return html`<ha-card .header=${config?.title ?? ""}>
      ${this._timerUi() ? renderLive(this._timerContext(texts)) : nothing}
      <div class="content ${config?.title ? "titled" : ""}">${this._renderBody(texts)}</div>
      ${this._toast
        ? html`<div class="toast" role="alert">
            <span>${this._toast}</span>
            <button type="button" @click=${() => {
              this._toast = "";
            }}>${texts.dismiss}</button>
          </div>`
        : nothing}
      ${this._renderDialog(texts)}
    </ha-card>`;
  }

  private _renderBody(texts: Texts): TemplateResult {
    if (!this._config?.entity) return html`<p class="state">${texts.choose_entity}</p>`;
    if (this._loadError) return html`<p class="state error">${texts[this._loadError]}</p>`;
    if (!this._payload) return html`<p class="state">${texts.loading}</p>`;
    const available = this._payload.available;
    const enabled = available && !this._offline;
    const groups = this._visibleGroups();
    const bars = this._renderBars(texts, this._offline);
    const banners = html`${this._renderTimerBar(texts)}${this._renderProposals(
      texts,
      enabled,
    )}${this._renderToolbar(texts, enabled)}${this._timerUi()
      ? renderSettings(this._timerContext(texts))
      : nothing}${bars}${!available
      ? html`<p class="banner" role="status">${texts.unavailable}</p>`
      : nothing}${this._offline
      ? html`<p class="banner" role="status">${texts.offline}</p>`
      : nothing}`;
    const closedProposals = this._renderClosedProposals(texts);
    if (groups.length === 0) {
      return available
        ? html`${banners}<p class="state empty">${texts.no_homework}</p>${closedProposals}`
        : html`${banners}${closedProposals}`;
    }
    const firstPast = groups.findIndex((group) => group.kind === "past");
    const planned = plannedMinutes(this._items());
    return html`${banners}<div class="days ${available ? "" : "stale"}">
        ${groups.map(
          (group, index) => html`
            ${index === firstPast
              ? html`<h3 class="section">${texts.earlier}</h3>`
              : nothing}
            <section class="day" aria-labelledby="day-${group.date}">
              <div class="day-head">
                <h4 id="day-${group.date}" class=${group.kind}>${this._dayTitle(group, texts)}</h4>
                ${this._renderPlanned(group, planned, texts)}${this._renderProposedMax(group, texts)}
              </div>
              <ul>
                ${group.entries.map((entry) => this._renderEntry(entry, texts, enabled))}
              </ul>
            </section>
          `,
        )}
      </div>${closedProposals}`;
  }

  /**
   * The planned time of a day, with a warning when it is above the effective daily maximum: the
   * override of that day (a coach circumstance) when there is one, else the maximum of that
   * weekday (an old payload: the single daily maximum). "Adjusted" means different from the
   * normal maximum of that weekday.
   */
  private _renderPlanned(
    group: EntryGroup,
    planned: ReadonlyMap<string, number>,
    texts: Texts,
  ): TemplateResult | typeof nothing {
    if (group.kind === "overdue") return nothing;
    const total = planned.get(group.date) ?? 0;
    if (total <= 0) return nothing;
    const lang = this._language() === "nl" ? "nl" : "en";
    const { max, adjusted } = dayMaximum(this._payload, group.date);
    const text = format(texts.sub.planned, { time: formatMinutes(total, lang) });
    if (typeof max !== "number") return html`<span class="planned">${text}</span>`;
    const over = total > max;
    if (!over && !adjusted) return html`<span class="planned">${text}</span>`;
    const maxText = formatMinutes(max, lang);
    // No reason is shown: the payload has none.
    const tip = format(
      over && max === 0
        ? adjusted
          ? texts.sub.over_zero_adjusted_max
          : texts.sub.over_zero_max
        : adjusted
          ? over
            ? texts.sub.over_adjusted_max
            : texts.sub.adjusted_max
          : texts.sub.over_max,
      { max: maxText },
    );
    const short = format(adjusted ? texts.sub.max_short_adjusted : texts.sub.max_short, {
      max: maxText,
    });
    const cls = ["planned", over ? "over" : "", adjusted ? "adjusted" : ""]
      .filter((c) => c !== "")
      .join(" ");
    return html`<span class=${cls} title=${tip}
      >${over ? html`<span aria-hidden="true">⚠ </span>` : nothing}${text}<span aria-hidden="true">
        ${short}</span
      ><span class="sr-only">, ${tip}</span></span
    >`;
  }

  /** "voorstel: max 2 u" on a day that an open period proposal covers (it has no effect yet). */
  private _renderProposedMax(
    group: EntryGroup,
    texts: Texts,
  ): TemplateResult | typeof nothing {
    if (group.kind === "overdue") return nothing;
    const minutes = proposedMaximum(this._proposals(), group.date);
    if (minutes === undefined) return nothing;
    const max = formatMinutes(minutes, this._language() === "nl" ? "nl" : "en");
    return html`<span class="proposed-max" title=${format(texts.proposal.day_note_aria, { max })}
      ><span aria-hidden="true">${format(texts.proposal.day_note, { max })}</span
      ><span class="sr-only">${format(texts.proposal.day_note_aria, { max })}</span></span
    >`;
  }

  /** The backend knows the study timer (1.10.0 and later): without it the card shows no timer controls. */
  private _timerUi(): boolean {
    const payload = this._payload;
    return payload !== undefined && (payload.timer !== undefined || payload.timer_settings !== undefined);
  }

  private _timerContext(texts: Texts): TimerContext {
    return {
      controller: this._timer,
      texts,
      language: this._language() === "nl" ? "nl" : "en",
      enabled: this._payload?.available === true && !this._offline,
    };
  }

  /** The timer at the top of the card: it shows whenever a timer exists, whichever day its subtask is on. */
  private _renderTimerBar(texts: Texts): TemplateResult | typeof nothing {
    if (!this._timerUi()) return nothing;
    const context = this._timerContext(texts);
    const view = this._timer.view();
    if (!view) return nothing;
    const lang = this._language() === "nl" ? "nl" : "en-GB";
    const meta = format(texts.timer.meta, {
      subject: view.timer.subject,
      label: this._timer.labelOf(view.timer.subtask),
      date: formatShortDay(view.timer.due, lang),
    });
    return html`<section class="timer-bar ${view.state}" aria-label=${texts.timer.region}>
      <div class="timer-bar-row">
        <div class="timer-bar-text">
          <span class="timer-bar-title">${view.timer.title}</span>
          <span class="meta">${meta}</span>
        </div>
        ${view.state === "finished"
          ? html`<span class="timer-state finished">${texts.timer.finished}</span>`
          : html`${renderCountdown(context, view, "bar-countdown")}${view.state === "paused"
              ? html`<span class="timer-state">${texts.timer.paused}</span>`
              : nothing}`}
        ${renderActions(context, view, "bar")}
      </div>
      <div class="timer-track" aria-hidden="true">
        <div class="timer-fill" style="width: ${Math.round(view.fraction * 100)}%"></div>
      </div>
      ${renderPanel(context)}
    </section>`;
  }

  /** The timer of one subtask row: countdown and buttons, or "Tijd is om" with Klaar, +x min and Nog niet. */
  private _renderRowTimer(subtask: Subtask, texts: Texts): TemplateResult | typeof nothing {
    if (!this._timerUi()) return nothing;
    const context = this._timerContext(texts);
    const view = this._timer.viewFor(subtask.uid);
    return html`${view
      ? html`<div class="timer-row ${view.state}">
          ${view.state === "finished"
            ? html`<span class="timer-state finished">${texts.timer.finished}</span>`
            : html`${renderCountdown(context, view)}${view.state === "paused"
                ? html`<span class="timer-state">${texts.timer.paused}</span>`
                : nothing}`}
          ${renderActions(context, view, "row")}
        </div>`
      : nothing}${renderReplaceConfirm(context, subtask.uid, subtask.title)}`;
  }

  private _renderToolbar(texts: Texts, enabled: boolean): TemplateResult {
    const labels = this._payload?.labels ?? [];
    const canAdd = enabled && labels.length > 0;
    const toggle = (
      name: "show_completed" | "show_past",
      pressed: boolean,
      text: string,
      tip: string,
    ): TemplateResult => html`<button
      type="button"
      class="switch ${pressed ? "on" : ""}"
      aria-pressed=${pressed ? "true" : "false"}
      title=${tip}
      aria-label=${tip}
      @click=${() => {
        this._setSwitch(name, !pressed);
      }}
    ><span aria-hidden="true" class="tick">${pressed ? "✓" : ""}</span>${text}</button>`;
    return html`<div class="toolbar" role="toolbar" aria-label=${texts.switches_label}>
      ${toggle("show_completed", this._showCompleted, texts.show_completed_switch, texts.show_completed_tip)}
      ${toggle("show_past", this._showPast, texts.show_past_switch, texts.show_past_tip)}
      ${this._timerUi() ? renderSettingsButton(this._timerContext(texts)) : nothing}
      ${canAdd
        ? html`<button
            type="button"
            class="add"
            title=${texts.add_label}
            aria-label=${texts.add_label}
            aria-haspopup="dialog"
            @click=${() => {
              this._dialogOpen = true;
            }}
          >+</button>`
        : nothing}
    </div>`;
  }

  private _renderDialog(texts: Texts): TemplateResult | typeof nothing {
    const payload = this._payload;
    const config = this._config;
    if (!this._dialogOpen || !payload || !config) return nothing;
    const today = this._currentDay();
    const bounds = dateBounds(payload.items, today, config.days_ahead);
    return html`<magister-label-dialog
      .hass=${this._hass}
      .entity=${config.entity}
      .labels=${payload.labels ?? []}
      .texts=${texts}
      .language=${this._language()}
      .today=${today}
      .min=${bounds.min}
      .max=${bounds.max}
      @dialog-closed=${this._closeDialog}
    ></magister-label-dialog>`;
  }

  /** The progress bars of the enabled periods (the values come from the progress sensors). */
  private _renderBars(texts: Texts, stale: boolean): TemplateResult | typeof nothing {
    const config = this._config;
    const progress = this._payload?.progress;
    const periods = PROGRESS_PERIODS.filter(({ option }) => config?.[option]);
    if (periods.length === 0) return nothing;
    return html`<div class="bars ${stale ? "stale" : ""}">
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
    const notes = item.manual_labels.filter((label) => label.note !== "");
    const confirm = this._confirm?.uid === item.uid ? this._confirm.label : undefined;
    const itemUid = item.uid;
    const classes = [
      "item",
      item.is_test ? "test" : "",
      item.completed ? "done" : "",
      item.disabled === true ? "disabled" : "",
      item.cancelled ? "cancelled" : "",
    ]
      .filter(Boolean)
      .join(" ");
    const derived = isDerived(item);
    return html`<li class=${classes} data-uid=${itemUid}>
      ${derived
        ? html`<input
            type="checkbox"
            .checked=${item.completed}
            disabled
            aria-label=${format(texts.sub.derived_check, { subject: item.subject })}
          />`
        : html`<input
            type="checkbox"
            .checked=${item.completed}
            ?disabled=${!enabled || item.disabled === true}
            aria-label=${format(item.completed ? texts.mark_open : texts.mark_done, {
              subject: item.subject,
            })}
            @change=${() => void this._setProgress(item.uid, toggleTarget(item))}
          />`}
      <div class="main">
        <div class="head">
          ${this._renderMagisterChip(item, texts, enabled)}
          ${item.manual_labels.map((label) => this._renderManualChip(item.uid, label, texts, enabled))}
          <span class="subject">${item.subject}</span>
          ${this._renderMarker(item, texts)}
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
        ${this._menu === item.uid ? this._renderMenu(item, texts) : nothing}
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
        ${notes.map(
          (label) =>
            html`<p class="note"><span class="note-label">${label.name}</span> ${label.note}</p>`,
        )}
        ${confirm
          ? html`<div
              class="confirm"
              role="group"
              aria-label=${format(texts.confirm_remove, { name: confirm.name })}
              @keydown=${(event: KeyboardEvent) => {
                if (event.key === "Escape") {
                  event.stopPropagation();
                  this._cancelRemove();
                }
              }}
            >
              <span>${format(texts.confirm_remove, { name: confirm.name })}</span>
              <button type="button" class="cancel" @click=${() => {
                this._cancelRemove();
              }}>${texts.confirm_no}</button>
              <button type="button" class="danger" ?disabled=${!enabled} @click=${() => {
                void this._removeLabel(item.uid, confirm);
              }}>${texts.confirm_yes}</button>
            </div>`
          : nothing}
        ${derived
          ? this._renderDerived(item, texts)
          : this._renderProgress(
              item,
              format(texts.progress_of, { subject: item.subject }),
              texts,
              enabled && item.disabled !== true,
            )}
        ${this._renderAddSubtask(item, texts, enabled)}
      </div>
    </li>`;
  }

  /** The marker of an item that has subtasks: an icon and the count, in the subtask colour. */
  private _renderMarker(item: HomeworkItem, texts: Texts): TemplateResult | typeof nothing {
    const count = item.disabled === true ? 0 : (item.subtasks?.length ?? 0);
    if (count === 0) return nothing;
    const one = count === 1;
    const label = format(one ? texts.sub.marker_aria_one : texts.sub.marker_aria, { n: count });
    return html`<span class="sub-marker" role="img" title=${label} aria-label=${label}
      ><svg viewBox="0 0 24 24" aria-hidden="true"><path d=${SUBTASKS_ICON}></path></svg
      ><span aria-hidden="true">${format(one ? texts.sub.marker_one : texts.sub.marker, { n: count })}</span></span
    >`;
  }

  private _renderEntry(entry: Entry, texts: Texts, enabled: boolean): TemplateResult {
    return entry.type === "item"
      ? this._renderItem(entry.item, texts, enabled)
      : this._renderSubtask(entry.subtask, entry.parent, texts, enabled);
  }

  // -- subtasks --

  private _findSubtask(uid: string): Subtask | undefined {
    for (const item of this._payload?.items ?? []) {
      const subtask = item.subtasks?.find((candidate) => candidate.uid === uid);
      if (subtask) return subtask;
    }
    return undefined;
  }

  /** The item (or subtask) an open form belongs to; undefined when it is gone. */
  private _formTarget(form: SubForm): HomeworkItem | undefined {
    const item = this._payload?.items.find((candidate) => candidate.uid === form.itemUid);
    if (!item || item.disabled === true) return undefined;
    if (form.mode === "edit" && !item.subtasks?.some((sub) => sub.uid === form.subUid)) return undefined;
    return item;
  }

  /** Allowed dates of a subtask of `item`; fixed to the item date when that is not in the future. */
  private _dateBounds(item: HomeworkItem): { min: string; max: string; fixed: boolean } {
    const today = this._currentDay();
    return item.date <= today
      ? { min: item.date, max: item.date, fixed: true }
      : { min: today, max: item.date, fixed: false };
  }

  private _clampDate(date: string, bounds: { min: string; max: string }): string {
    return date < bounds.min ? bounds.min : date > bounds.max ? bounds.max : date;
  }

  /** The name of an item's (effective) label, for the reference of its subtasks. */
  private _itemLabel(item: HomeworkItem, texts: Texts): string {
    return effectiveLabel(item, texts);
  }

  private _renderDerived(item: HomeworkItem, texts: Texts): TemplateResult {
    const subtasks = item.subtasks ?? [];
    const done = subtasks.filter((subtask) => subtask.completed).length;
    const count = format(subtasks.length === 1 ? texts.sub.count_one : texts.sub.count, {
      done,
      total: subtasks.length,
    });
    const value = format(texts.percent, { n: item.progress });
    return html`<div class="progress derived">
      <div
        class="track"
        role="progressbar"
        aria-label=${format(texts.progress_of, { subject: item.subject })}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow=${item.progress}
        aria-valuetext=${format(texts.sub.derived_value, { count, n: item.progress })}
        title=${texts.sub.derived_hint}
      >
        <div class="fill" style="width: ${item.progress}%"></div>
      </div>
      <span class="percent">${value}</span>
      <span class="meta sub-count">${count}</span>
    </div>`;
  }

  private _renderAddSubtask(item: HomeworkItem, texts: Texts, enabled: boolean): TemplateResult | typeof nothing {
    if (item.disabled === true) return nothing;
    const form = this._form;
    const open = form?.mode === "add" && form.itemUid === item.uid;
    return html`${enabled
      ? html`<button
          type="button"
          class="link add-sub"
          data-add-sub=${item.uid}
          aria-expanded=${open ? "true" : "false"}
          aria-label=${format(texts.sub.add_aria, { subject: item.subject })}
          @click=${() => {
            this._openForm({ mode: "add", itemUid: item.uid }, item);
          }}
        >${texts.sub.add}</button>`
      : nothing}${open ? this._renderSubForm(form, item, texts) : nothing}`;
  }

  private _renderSubtask(
    subtask: Subtask,
    parent: HomeworkItem,
    texts: Texts,
    enabled: boolean,
  ): TemplateResult {
    const lang = this._language() === "nl" ? "nl" : "en-GB";
    const form = this._form;
    const editing = form?.mode === "edit" && form.subUid === subtask.uid ? form : undefined;
    const confirming = this._subConfirm === subtask.uid;
    const reference = format(texts.sub.for_item, {
      label: this._itemLabel(parent, texts),
      subject: parent.subject,
      date: formatShortDay(parent.date, lang),
    }).replace(/\s+/g, " ");
    const classes = [
      "item",
      "subtask",
      subtask.completed ? "done" : "",
      subtask.overdue ? "overdue" : "",
    ]
      .filter(Boolean)
      .join(" ");
    return html`<li class=${classes} data-uid=${subtask.uid}>
      <input
        type="checkbox"
        .checked=${subtask.completed}
        ?disabled=${!enabled}
        aria-label=${format(subtask.completed ? texts.sub.mark_open : texts.sub.mark_done, {
          title: subtask.title,
        })}
        @change=${() => void this._setProgress(subtask.uid, toggleTarget(subtask))}
      />
      <div class="main">
        ${editing
          ? this._renderSubForm(editing, parent, texts)
          : html`<div class="head">
              <span class="arrow" aria-hidden="true">↳</span>
              <span class="subject sub-title">${subtask.title}</span>
              ${subtask.created_by === "ai"
                ? html`<span
                    class="ai-badge"
                    role="img"
                    title=${texts.sub.ai_label}
                    aria-label=${texts.sub.ai_label}
                  ><span aria-hidden="true">${texts.sub.ai}</span></span>`
                : subtask.created_by === "parent"
                  ? html`<span
                      class="ai-badge parent-badge"
                      role="img"
                      title=${texts.sub.parent_label}
                      aria-label=${texts.sub.parent_label}
                    ><span aria-hidden="true">${texts.sub.parent}</span></span>`
                  : nothing}
              ${typeof subtask.minutes === "number"
                ? html`<span class="sub-minutes"
                    ><span class="sr-only">${texts.sub.minutes}: </span>${formatMinutes(
                      subtask.minutes,
                      this._language() === "nl" ? "nl" : "en",
                    )}</span
                  >`
                : nothing}
              ${enabled
                ? html`<span class="sub-actions">${this._timerUi() &&
                    typeof subtask.minutes === "number" &&
                    !subtask.completed &&
                    !this._timer.viewFor(subtask.uid)
                      ? renderStartButton(this._timerContext(texts), subtask.uid, subtask.title, subtask.minutes)
                      : nothing}<button
                      type="button"
                      class="icon-btn"
                      data-edit=${subtask.uid}
                      title=${texts.sub.edit}
                      aria-label=${format(texts.sub.edit_aria, { title: subtask.title })}
                      @click=${() => {
                        this._openForm({ mode: "edit", itemUid: parent.uid, subUid: subtask.uid }, parent);
                      }}
                    >✎</button>
                    <button
                      type="button"
                      class="icon-btn"
                      data-delete=${subtask.uid}
                      title=${texts.sub.delete}
                      aria-label=${format(texts.sub.delete_aria, { title: subtask.title })}
                      @click=${() => {
                        this._askDeleteSubtask(subtask.uid);
                      }}
                    >✕</button></span>`
                : nothing}
            </div>
            <div class="meta ref">${subtask.overdue
              ? html`<span class="badge">${texts.sub.overdue}</span> `
              : nothing}${reference}</div>`}
        ${confirming
          ? html`<div
              class="confirm subconfirm"
              role="group"
              aria-label=${format(texts.sub.confirm_delete, { title: subtask.title })}
              @keydown=${(event: KeyboardEvent) => {
                if (event.key === "Escape") {
                  event.stopPropagation();
                  this._cancelDeleteSubtask(subtask.uid);
                }
              }}
            >
              <span>${format(texts.sub.confirm_delete, { title: subtask.title })}</span>
              <button type="button" class="cancel" @click=${() => {
                this._cancelDeleteSubtask(subtask.uid);
              }}>${texts.confirm_no}</button>
              <button type="button" class="danger" ?disabled=${!enabled} @click=${() => {
                void this._deleteSubtask(subtask.uid);
              }}>${texts.sub.confirm_yes}</button>
            </div>`
          : nothing}
        ${this._renderRowTimer(subtask, texts)}
        ${this._renderProgress(
          subtask,
          format(texts.sub.progress_of, { title: subtask.title }),
          texts,
          enabled,
        )}
      </div>
    </li>`;
  }

  private _renderSubForm(form: SubForm, item: HomeworkItem, texts: Texts): TemplateResult {
    const bounds = this._dateBounds(item);
    const name =
      form.mode === "add"
        ? format(texts.sub.form_add, { subject: item.subject })
        : format(texts.sub.form_edit, {
            title: item.subtasks?.find((sub) => sub.uid === form.subUid)?.title ?? "",
          });
    const errorId = `sub-error-${form.mode}`;
    return html`<form
      class="subform"
      aria-label=${name}
      novalidate
      @submit=${(event: Event) => {
        event.preventDefault();
        void this._submitForm();
      }}
      @keydown=${(event: KeyboardEvent) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          this._cancelForm();
        }
      }}
    >
      <label>
        <span>${texts.sub.title}</span>
        <input
          class="sub-title-input"
          type="text"
          required
          maxlength=${MAX_TITLE}
          .value=${form.title}
          ?disabled=${form.busy}
          aria-invalid=${form.error ? "true" : "false"}
          aria-describedby=${form.error ? errorId : nothing}
          @input=${(event: Event) => {
            this._patchForm({ title: (event.target as HTMLInputElement).value, error: "" });
          }}
        />
      </label>
      <label>
        <span>${bounds.fixed ? texts.sub.date_fixed : texts.sub.date}</span>
        <input
          class="sub-date-input"
          type="date"
          .value=${bounds.fixed ? bounds.max : form.date}
          min=${bounds.min}
          max=${bounds.max}
          ?disabled=${form.busy || bounds.fixed}
          @input=${(event: Event) => {
            this._patchForm({ date: (event.target as HTMLInputElement).value, error: "" });
          }}
        />
      </label>
      <label>
        <span>${texts.sub.minutes}</span>
        <select
          class="sub-minutes-input"
          ?disabled=${form.busy}
          @change=${(event: Event) => {
            const value = (event.target as HTMLSelectElement).value;
            this._patchForm({ minutes: value === "" ? null : Number(value), error: "" });
          }}
        >
          <option value="">${texts.sub.minutes_none}</option>
          ${minuteChoices(form.minutes, form.storedMinutes).map(
            (value) =>
              html`<option value=${String(value)} ?selected=${form.minutes === value}>${formatMinutes(
                value,
                this._language() === "nl" ? "nl" : "en",
              )}</option>`,
          )}
        </select>
      </label>
      ${form.error
        ? html`<p class="form-error" id=${errorId} role="alert">${form.error}</p>`
        : nothing}
      <div class="form-actions">
        <button type="button" class="cancel" ?disabled=${form.busy} @click=${() => {
          this._cancelForm();
        }}>${texts.sub.cancel}</button>
        <button type="submit" class="primary" ?disabled=${form.busy}>${form.busy
          ? texts.sub.saving
          : texts.sub.save}</button>
      </div>
    </form>`;
  }

  private _patchForm(patch: Partial<SubForm>): void {
    if (this._form) this._form = { ...this._form, ...patch };
  }

  private _openForm(
    target: { mode: "add"; itemUid: string } | { mode: "edit"; itemUid: string; subUid: string },
    item: HomeworkItem,
  ): void {
    this._confirm = undefined;
    this._subConfirm = undefined;
    this._closeMenu(false);
    const bounds = this._dateBounds(item);
    const sub = target.mode === "edit" ? item.subtasks?.find((s) => s.uid === target.subUid) : undefined;
    this._form = {
      ...target,
      title: sub?.title ?? "",
      date: sub ? this._clampDate(sub.planned, bounds) : bounds.fixed ? bounds.max : bounds.min,
      minutes: sub?.minutes ?? null,
      storedMinutes: sub?.minutes ?? null,
      error: "",
      busy: false,
    };
    this._focusForm = true;
  }

  private _cancelForm(): void {
    const form = this._form;
    if (!form || form.busy) return;
    this._form = undefined;
    const selector =
      form.mode === "add"
        ? `[data-add-sub="${CSS.escape(form.itemUid)}"]`
        : `[data-edit="${CSS.escape(form.subUid ?? "")}"]`;
    void this.updateComplete.then(() => {
      this.shadowRoot?.querySelector<HTMLElement>(selector)?.focus();
    });
  }

  private _formError(form: SubForm, code: string | undefined): void {
    const errors = this._texts().sub.errors;
    this._form = { ...form, busy: false, error: (code ? errors[code] : undefined) ?? errors.default ?? "" };
    this._focusForm = true;
  }

  private async _submitForm(): Promise<void> {
    const form = this._form;
    const hass = this._hass;
    const entity = this._config?.entity;
    if (!form || form.busy || !hass || !entity || !this._payload?.available || this._offline) return;
    const item = this._items().find((candidate) => candidate.uid === form.itemUid);
    if (!item) return;
    const title = form.title.trim();
    if (title === "" || title.length > MAX_TITLE) {
      this._formError(form, "invalid_format");
      return;
    }
    const bounds = this._dateBounds(item);
    if (form.mode === "add") {
      const date = bounds.fixed ? bounds.max : form.date;
      if (date < bounds.min || date > bounds.max) {
        this._formError(form, "invalid_date");
        return;
      }
      // The add waits for the answer instead of being optimistic: the backend assigns the
      // subtask's id, and a refusal (too many, bad date) must keep the form with its input.
      this._form = { ...form, busy: true, error: "" };
      try {
        const result = await hass.callWS<SubtaskResult>({
          type: ADD_SUBTASK,
          entity_id: entity,
          item: item.uid,
          title,
          date,
          ...(form.minutes !== null ? { minutes: form.minutes } : {}),
        });
        const known = new Set((item.subtasks ?? []).map((sub) => sub.uid));
        const created = (result.subtasks ?? []).filter((sub) => !known.has(sub.uid)).pop();
        this._form = undefined;
        this._pendingFocus = created?.uid ?? result.subtasks?.at(-1)?.uid;
      } catch (error) {
        this._formError({ ...form, title: form.title }, (error as WsError | undefined)?.code);
      }
      return;
    }
    const subtask = item.subtasks?.find((candidate) => candidate.uid === form.subUid);
    if (!subtask) return;
    const edit: SubtaskEdit = {};
    if (title !== subtask.title) edit.title = title;
    if (!bounds.fixed && form.date !== this._clampDate(subtask.planned, bounds)) {
      if (form.date < bounds.min || form.date > bounds.max) {
        this._formError(form, "invalid_date");
        return;
      }
      edit.planned = form.date;
    }
    if (form.minutes !== (subtask.minutes ?? null)) edit.minutes = form.minutes;
    if (edit.title === undefined && edit.planned === undefined && edit.minutes === undefined) {
      this._cancelForm();
      return;
    }
    this._form = undefined;
    this._focusAfter([`[data-edit="${CSS.escape(subtask.uid)}"]`]);
    await this._changeSubtask(subtask.uid, edit, {
      type: UPDATE_SUBTASK,
      entity_id: entity,
      subtask: subtask.uid,
      ...(edit.title !== undefined ? { title: edit.title } : {}),
      ...(edit.planned !== undefined ? { date: edit.planned } : {}),
      ...(edit.minutes !== undefined ? { minutes: edit.minutes } : {}),
    }, form);
  }

  /** Apply an optimistic subtask edit or deletion, send it, and roll back when it fails. */
  private async _changeSubtask(
    uid: string,
    edit: SubtaskEdit,
    message: Record<string, unknown>,
    form?: SubForm,
  ): Promise<void> {
    const hass = this._hass;
    if (!hass) return;
    const token = ++this._nextToken;
    this._subTokens.set(uid, token);
    this._subEdits = new Map(this._subEdits).set(uid, edit);
    try {
      await hass.callWS<SubtaskResult>(message);
      if (this._subTokens.get(uid) !== token) return;
      this._subTokens.delete(uid);
      // The push usually arrived first; otherwise keep the change until it does.
      if (reflectsEdit(this._findSubtask(uid), edit)) {
        const next = new Map(this._subEdits);
        next.delete(uid);
        this._subEdits = next;
      }
    } catch (error) {
      if (this._subTokens.get(uid) !== token) return;
      this._subTokens.delete(uid);
      const next = new Map(this._subEdits);
      next.delete(uid);
      this._subEdits = next;
      const code = (error as WsError | undefined)?.code;
      if (form && !this._form && this._formTarget(form)) {
        // An edit comes back as the form it was sent from, with the reason inline.
        this._formError({ ...form, busy: false }, code);
      } else {
        const errors = this._texts().sub.errors;
        this._showToast((code ? errors[code] : undefined) ?? this._texts().save_failed);
      }
    }
  }

  private _askDeleteSubtask(uid: string): void {
    this._form = undefined;
    this._confirm = undefined;
    this._subConfirm = uid;
    void this.updateComplete.then(() => {
      this.shadowRoot?.querySelector<HTMLElement>(".subconfirm .cancel")?.focus();
    });
  }

  private _cancelDeleteSubtask(uid: string): void {
    this._subConfirm = undefined;
    void this.updateComplete.then(() => {
      this.shadowRoot?.querySelector<HTMLElement>(`[data-delete="${CSS.escape(uid)}"]`)?.focus();
    });
  }

  private async _deleteSubtask(uid: string): Promise<void> {
    const entity = this._config?.entity;
    this._subConfirm = undefined;
    if (!entity || !this._hass || !this._payload?.available || this._offline) return;
    // The focused buttons vanish with the row: the next row, the previous one, else the item's add button.
    const row = this.shadowRoot?.querySelector(`li[data-uid="${CSS.escape(uid)}"]`);
    const around = [row?.nextElementSibling, row?.previousElementSibling]
      .map((sibling) => sibling?.getAttribute("data-uid"))
      .filter((value): value is string => typeof value === "string");
    this._focusAfter([
      ...around.map((other) => `li[data-uid="${CSS.escape(other)}"] input[type="checkbox"]`),
      `[data-add-sub="${CSS.escape(parentUid(uid))}"]`,
      ".add",
    ]);
    await this._changeSubtask(uid, { deleted: true }, {
      type: DELETE_SUBTASK,
      entity_id: entity,
      subtask: uid,
    });
  }

  /** After the next render, focus the first of these selectors that exists. */
  private _focusAfter(selectors: string[]): void {
    void this.updateComplete.then(() => {
      for (const selector of selectors) {
        const element = this.shadowRoot?.querySelector<HTMLElement>(selector);
        if (element) {
          element.focus();
          return;
        }
      }
    });
  }

  protected override updated(): void {
    this._timer.afterRender();
    // The estimate select shows the form's value (the options are rendered before it is set).
    const select = this.shadowRoot?.querySelector<HTMLSelectElement>(".subform .sub-minutes-input");
    const wanted = this._form?.minutes === null ? "" : String(this._form?.minutes ?? "");
    if (select && this._form && select.value !== wanted) select.value = wanted;
    if (this._focusForm && this._form) {
      this._focusForm = false;
      this.shadowRoot?.querySelector<HTMLElement>(".subform .sub-title-input")?.focus();
    }
    if (this._pendingFocus) {
      const row = this.shadowRoot?.querySelector<HTMLElement>(
        `li[data-uid="${CSS.escape(this._pendingFocus)}"] input[type="checkbox"]`,
      );
      if (row) {
        this._pendingFocus = undefined;
        row.focus();
      } else if (this._findSubtask(this._pendingFocus)) {
        // The new subtask is in the state but not on screen (beyond the days shown): the
        // item's add button takes the focus, so it is not lost.
        const target = parentUid(this._pendingFocus);
        this._pendingFocus = undefined;
        this.shadowRoot?.querySelector<HTMLElement>(`[data-add-sub="${CSS.escape(target)}"]`)?.focus();
      }
    }
  }

  /**
   * The Magister chip. With a working connection it is a menu button (replace, disable,
   * restore). An overridden chip is struck through, with a hidden word that says why,
   * and a replacement chip follows (in the manual style, without a remove button).
   */
  private _renderMagisterChip(
    item: HomeworkItem,
    texts: Texts,
    enabled: boolean,
  ): TemplateResult | typeof nothing {
    if (item.info_type === null) return nothing;
    const override = item.override ?? null;
    const name = typeLabel(texts, item.info_type, item.label ?? "");
    const state = override?.mode === "replace" ? texts.override_replaced : texts.override_disabled;
    const classes = `chip magister ${override ? "overridden" : item.info_type >= 2 ? "test" : ""}`;
    const content = override
      ? html`<s>${name}</s><span class="sr-only"> ${state}</span>`
      : html`${name}`;
    const chip = enabled
      ? html`<button
          type="button"
          class=${classes}
          data-menu-button=${item.uid}
          aria-haspopup="menu"
          aria-expanded=${this._menu === item.uid ? "true" : "false"}
          title=${texts.override_tip}
          @click=${() => {
            if (this._menu === item.uid) this._closeMenu(true);
            else this._openMenu(item.uid, "first");
          }}
          @keydown=${(event: KeyboardEvent) => {
            this._onChipKey(event, item.uid);
          }}
        >${content}</button>`
      : html`<span class=${classes}>${content}</span>`;
    const replacement =
      override?.mode === "replace"
        ? html`<span class="chip manual plain ${override.label.kind === "test" ? "test" : ""}"
            >${override.label.name}</span
          >`
        : nothing;
    return html`${chip}${replacement}`;
  }

  private _renderMenu(item: HomeworkItem, texts: Texts): TemplateResult {
    const actions = menuActions(item, this._payload?.labels ?? []);
    const entry = (text: string, aria: string, change: OverrideChange): TemplateResult =>
      html`<button
        type="button"
        role="menuitem"
        tabindex="-1"
        aria-label=${aria}
        @click=${() => {
          this._choose(item, change);
        }}
      >${text}</button>`;
    return html`<div
      class="menu"
      role="menu"
      aria-label=${format(texts.override_menu, { subject: item.subject })}
      @keydown=${(event: KeyboardEvent) => {
        this._onMenuKey(event, item.uid);
      }}
    >
      ${actions.replace.length > 0
        ? html`<div role="group" aria-label=${texts.override_replace_with}>
            <span class="menu-heading" aria-hidden="true">${texts.override_replace_with}</span>
            ${actions.replace.map((option) =>
              entry(
                option.name,
                format(texts.override_replace_option, { name: option.name }),
                { mode: "replace", label: option },
              ),
            )}
          </div>`
        : nothing}
      ${actions.disable
        ? entry(texts.override_disable, texts.override_disable, { mode: "disable" })
        : nothing}
      ${actions.restore
        ? entry(texts.override_restore, texts.override_restore, { mode: "clear" })
        : nothing}
    </div>`;
  }

  private _renderManualChip(
    uid: string,
    label: ManualLabel,
    texts: Texts,
    enabled: boolean,
  ): TemplateResult {
    return html`<span class="chip manual ${label.kind === "test" ? "test" : ""}"
      >${label.name}<button
        type="button"
        class="chip-remove"
        data-key=${labelKey(uid, label.id)}
        aria-label=${format(texts.remove_label, { name: label.name })}
        title=${format(texts.remove_label, { name: label.name })}
        ?disabled=${!enabled}
        @click=${() => {
          this._askRemove(uid, label);
        }}
      >×</button></span
    >`;
  }

  private _renderProgress(
    item: { uid: string; progress: number },
    label: string,
    texts: Texts,
    enabled: boolean,
  ): TemplateResult {
    // A stored value between the steps (say 40 %) leaves every radio unchecked; the
    // nearest step takes the tab stop and the tint.
    const nearest = snapToStep(item.progress);
    const exact = (STEPS as readonly number[]).includes(item.progress);
    return html`<div class="progress">
      <div
        class="segments"
        role="radiogroup"
        aria-label=${label}
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

  static override styles = [
    timerStyles,
    css`
    :host {
      display: block;
      /* Subtasks and proposals: one colour. The text variant mixes in the text colour, so it
         keeps its contrast on the light tint (light theme) and on the dark card (dark theme). */
      --sub-color: var(--info-color, #039be5);
      --sub-text: color-mix(in srgb, var(--sub-color) 55%, var(--primary-text-color, #212121));
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
    .bars.stale {
      opacity: 0.55;
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
    .item.subtask {
      border-left-color: var(--sub-color);
      background: color-mix(in srgb, var(--sub-color) 10%, transparent);
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
    .chip.manual {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      padding-right: 2px;
      background: transparent;
      color: var(--primary-color);
      border: 1.5px solid var(--primary-color);
    }
    button.chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      min-height: 28px;
      font: inherit;
      font-size: 0.75em;
      font-weight: 500;
      cursor: pointer;
    }
    button.chip.test {
      font-weight: 700;
    }
    button.chip::after {
      content: "\\25be";
      content: "\\25be" / "";
      font-size: 0.9em;
      opacity: 0.8;
    }
    .chip.overridden {
      font-weight: 500;
      color: var(--secondary-text-color);
      background: var(--secondary-background-color);
      border-color: var(--divider-color);
    }
    .chip.overridden s {
      text-decoration: line-through;
    }
    .chip.manual.plain {
      padding-right: 8px;
    }
    .menu {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 2px;
      margin-top: 6px;
      padding: 4px;
      max-width: 320px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      background: var(--card-background-color, var(--ha-card-background, #fff));
    }
    .menu [role="group"] {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .menu-heading {
      padding: 4px 8px 0;
      font-size: 0.75em;
      color: var(--secondary-text-color);
    }
    .menu [role="menuitem"] {
      min-height: 40px;
      padding: 0 12px;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.9em;
      text-align: left;
      cursor: pointer;
    }
    .menu [role="menuitem"]:hover,
    .menu [role="menuitem"]:focus-visible {
      background: color-mix(in srgb, var(--primary-color) 14%, transparent);
    }
    .menu [role="menuitem"]:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: -2px;
    }
    .item.disabled .subject,
    .item.disabled .percent {
      opacity: 0.7;
    }
    .chip.manual.test {
      color: var(--warning-color, #ffa600);
      border-color: var(--warning-color, #ffa600);
      background: transparent;
    }
    .chip-remove {
      min-width: 24px;
      min-height: 24px;
      padding: 0;
      border: none;
      border-radius: 50%;
      background: none;
      color: inherit;
      font: inherit;
      font-size: 1.2em;
      line-height: 1;
      cursor: pointer;
    }
    .chip-remove:disabled {
      cursor: default;
      opacity: 0.5;
    }
    .note {
      margin: 4px 0 0;
      font-size: 0.9em;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--secondary-text-color);
    }
    .note-label {
      font-weight: 500;
      color: var(--primary-text-color);
    }
    .confirm {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-top: 6px;
      padding: 6px 8px;
      border-radius: 8px;
      background: color-mix(in srgb, var(--error-color) 12%, transparent);
      font-size: 0.9em;
    }
    .confirm button,
    .switch,
    .add {
      min-height: 36px;
      padding: 0 12px;
      border-radius: 18px;
      border: 1px solid var(--divider-color);
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .confirm .danger {
      border-color: var(--error-color);
      background: var(--error-color);
      color: var(--text-primary-color, #fff);
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin: 0 0 12px;
    }
    .switch.on {
      border-color: var(--primary-color);
      background: color-mix(in srgb, var(--primary-color) 18%, transparent);
      color: var(--primary-color);
      font-weight: 500;
    }
    .switch .tick {
      display: inline-block;
      min-width: 1em;
    }
    .add {
      margin-left: auto;
      min-width: 36px;
      padding: 0;
      font-size: 1.4em;
      line-height: 1;
      border-color: var(--primary-color);
      color: var(--primary-color);
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
    .ai-badge {
      flex: 0 0 auto;
      padding: 0 6px;
      border-radius: 10px;
      font-size: 0.7em;
      font-weight: 600;
      line-height: 1.6;
      letter-spacing: 0.04em;
      color: var(--primary-color);
      border: 1px solid var(--primary-color);
    }
    .parent-badge {
      color: var(--secondary-text-color);
      border-color: var(--secondary-text-color);
    }
    .sub-minutes {
      flex: 0 0 auto;
      font-size: 0.85em;
      color: var(--secondary-text-color);
      white-space: nowrap;
    }
    .day-head {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      column-gap: 12px;
    }
    .planned {
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .planned.adjusted {
      text-decoration: underline dotted;
      text-underline-offset: 3px;
    }
    .planned.over {
      padding: 0 8px;
      border: 1px solid var(--warning-color, #ffa600);
      border-radius: 10px;
      background: color-mix(in srgb, var(--warning-color, #ffa600) 15%, transparent);
      color: var(--primary-text-color);
      font-weight: 600;
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
    .toast button:focus-visible,
    .confirm button:focus-visible,
    .proposal button:focus-visible,
    .chip-remove:focus-visible,
    button.chip:focus-visible,
    .switch:focus-visible,
    .add:focus-visible {
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
    h4.overdue {
      color: var(--error-color);
    }
    .arrow {
      color: var(--sub-text);
    }
    .sub-marker {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      flex: 0 0 auto;
      padding: 0 7px 0 4px;
      border-radius: 10px;
      border: 1px solid color-mix(in srgb, var(--sub-color) 60%, transparent);
      background: color-mix(in srgb, var(--sub-color) 12%, transparent);
      color: var(--sub-text);
      font-size: 0.75em;
      font-weight: 500;
      line-height: 1.6;
      white-space: nowrap;
    }
    .sub-marker svg {
      width: 14px;
      height: 14px;
      fill: currentColor;
    }
    .proposals {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0 0 12px;
    }
    .proposal {
      padding: 8px 12px;
      border-left: 3px solid var(--sub-color);
      border-radius: 4px 8px 8px 4px;
      background: color-mix(in srgb, var(--sub-color) 10%, transparent);
    }
    .proposal-text {
      margin: 0 0 8px;
      overflow-wrap: anywhere;
    }
    .proposal-title {
      font-weight: 600;
      color: var(--sub-text);
    }
    .nowrap {
      white-space: nowrap;
    }
    .proposal-expires {
      display: block;
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .proposal-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .proposal-actions button {
      min-height: 36px;
      padding: 0 14px;
      border-radius: 18px;
      border: 1px solid var(--divider-color);
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .proposal .primary {
      border-color: var(--primary-color);
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .proposal button:disabled {
      cursor: default;
      opacity: 0.6;
    }
    .proposal .confirm {
      margin-top: 0;
      background: color-mix(in srgb, var(--sub-color) 16%, transparent);
    }
    .proposed-max {
      font-size: 0.85em;
      color: var(--sub-text);
      font-weight: 500;
    }
    .closed-proposals {
      margin-top: 8px;
    }
    .closed-proposal {
      display: flex;
      flex-wrap: wrap;
      gap: 2px 8px;
      padding: 6px 0 6px 8px;
      border-left: 3px solid var(--sub-color);
      font-size: 0.9em;
      color: var(--secondary-text-color);
      overflow-wrap: anywhere;
    }
    .proposal-status {
      font-weight: 600;
      color: var(--sub-text);
    }
    .item.subtask {
      padding-left: 24px;
      padding-right: 8px;
    }
    .item.overdue .ref {
      color: var(--error-color);
    }
    .ref {
      overflow-wrap: anywhere;
    }
    .progress.derived {
      flex-wrap: wrap;
      padding-right: 8px;
      row-gap: 2px;
    }
    .progress.derived .track {
      flex: 1 1 120px;
      max-width: 260px;
      margin: 0;
    }
    .sub-actions {
      display: inline-flex;
      margin-left: auto;
      white-space: nowrap;
    }
    .sub-title {
      flex: 1 1 8em;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .sub-count {
      flex: 0 1 auto;
      min-width: 0;
    }
    .icon-btn,
    button.link {
      min-height: 32px;
      min-width: 32px;
      padding: 0 6px;
      border: none;
      background: none;
      color: var(--primary-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .icon-btn {
      color: var(--secondary-text-color);
    }
    button.link {
      display: block;
      margin-top: 4px;
      padding: 0;
    }
    .icon-btn:focus-visible,
    button.link:focus-visible,
    .subform button:focus-visible,
    .subform input:focus-visible,
    .subform select:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    .subform {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 6px;
      padding: 8px;
      max-width: 360px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
    }
    .subform label {
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 0.8em;
      color: var(--secondary-text-color);
    }
    .subform input,
    .subform select {
      min-height: 36px;
      padding: 0 8px;
      border: 1px solid var(--divider-color);
      border-radius: 6px;
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 1.1em;
    }
    .form-error {
      margin: 0;
      font-size: 0.85em;
      color: var(--error-color);
    }
    .form-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
    .form-actions button {
      min-height: 36px;
      padding: 0 14px;
      border-radius: 18px;
      border: 1px solid var(--divider-color);
      background: transparent;
      color: var(--primary-text-color);
      font: inherit;
      font-size: 0.85em;
      cursor: pointer;
    }
    .form-actions .primary {
      border-color: var(--primary-color);
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .form-actions button:disabled {
      cursor: default;
      opacity: 0.6;
    }
    @media (max-width: 480px) {
      .segments {
        flex: 1 1 auto;
      }
      .segment {
        min-height: 40px;
      }
    }
    .timer-bar {
      margin: 0 0 12px;
      padding: 8px 12px 10px;
      border-left: 3px solid var(--timer-color);
      border-radius: 4px 8px 8px 4px;
      background: color-mix(in srgb, var(--timer-color) 10%, transparent);
    }
    .timer-bar.finished {
      border-left-color: var(--timer-warn);
      background: color-mix(in srgb, var(--timer-warn) 14%, transparent);
    }
    .timer-bar-row,
    .timer-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px 10px;
    }
    .timer-bar-text {
      display: flex;
      flex: 1 1 10em;
      flex-direction: column;
      min-width: 0;
    }
    .timer-bar-title {
      font-weight: 600;
      overflow-wrap: anywhere;
    }
    .bar-countdown {
      font-size: 1.5em;
    }
    .timer-row {
      margin-top: 6px;
    }
    .timer-state {
      padding: 0 8px;
      border-radius: 10px;
      border: 1px solid var(--divider-color);
      font-size: 0.8em;
      font-weight: 500;
      color: var(--secondary-text-color);
    }
    .timer-state.finished {
      border-color: var(--timer-warn);
      color: var(--primary-text-color);
      font-weight: 700;
    }
    .timer-settings-btn {
      margin-left: auto;
    }
    .timer-settings-btn + .add {
      margin-left: 0;
    }
  `,
  ];
}
