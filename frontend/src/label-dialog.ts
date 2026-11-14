import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import { formatDay, timeRange } from "./logic";
import { format, typeLabel, type Language, type Texts } from "./translations";
import type { Appointment, Hass, LabelOption, WsError } from "./types";

const APPOINTMENTS = "magister/homework/appointments";
const ADD_LABEL = "magister/homework/add_label";
export const NOTE_MAX = 200;

interface AppointmentsResult {
  appointments: Appointment[];
}

/**
 * The add-label dialog: a day, one of its lessons, a label and an optional note.
 * A native modal <dialog>: focus stays inside, Escape closes, the page behind is inert.
 * Fires `label-added` after a successful save and `dialog-closed` whenever it closes.
 */
export class MagisterLabelDialog extends LitElement {
  static override properties = {
    hass: { attribute: false },
    entity: { attribute: false },
    labels: { attribute: false },
    texts: { attribute: false },
    language: { attribute: false },
    today: { attribute: false },
    min: { attribute: false },
    max: { attribute: false },
    _date: { state: true },
    _appointments: { state: true },
    _loading: { state: true },
    _loadError: { state: true },
    _selected: { state: true },
    _label: { state: true },
    _note: { state: true },
    _saving: { state: true },
    _error: { state: true },
  };

  declare hass: Hass | undefined;
  declare entity: string;
  declare labels: LabelOption[];
  declare texts: Texts;
  declare language: Language;
  declare today: string;
  declare min: string;
  declare max: string;
  declare _date: string;
  declare _appointments: Appointment[];
  declare _loading: boolean;
  declare _loadError: string;
  declare _selected: string;
  declare _label: string;
  declare _note: string;
  declare _saving: boolean;
  declare _error: string;

  private _request = 0;
  private _closedSent = false;

  constructor() {
    super();
    this._date = "";
    this._appointments = [];
    this._loading = false;
    this._loadError = "";
    this._selected = "";
    this._label = "";
    this._note = "";
    this._saving = false;
    this._error = "";
  }

  override connectedCallback(): void {
    super.connectedCallback();
    this._date = this.today;
  }

  protected override firstUpdated(): void {
    const dialog = this._dialog();
    if (dialog) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    void this._load(this._date);
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._request++;
  }

  private _dialog(): HTMLDialogElement | null {
    return this.renderRoot.querySelector("dialog");
  }

  private _close(): void {
    const dialog = this._dialog();
    if (dialog?.open) dialog.close();
    this._emitClosed();
  }

  /** Once per dialog, whether it closed through us or natively. */
  private _emitClosed(): void {
    if (this._closedSent) return;
    this._closedSent = true;
    this.dispatchEvent(new CustomEvent("dialog-closed", { bubbles: true, composed: true }));
  }

  private async _load(date: string): Promise<void> {
    const hass = this.hass;
    const request = ++this._request;
    this._appointments = [];
    this._selected = "";
    this._loadError = "";
    this._error = "";
    if (!hass || !date) {
      this._loading = false;
      return;
    }
    this._loading = true;
    try {
      const result = await hass.callWS<AppointmentsResult>({
        type: APPOINTMENTS,
        entity_id: this.entity,
        date,
      });
      if (request !== this._request) return;
      this._appointments = result.appointments;
    } catch (error) {
      if (request !== this._request) return;
      this._loadError = this._message(error, this.texts.label_errors["load_default"] ?? "");
    } finally {
      if (request === this._request) this._loading = false;
    }
  }

  private _message(error: unknown, fallback: string): string {
    const code = (error as WsError | undefined)?.code;
    return (code ? this.texts.label_errors[code] : undefined) ?? fallback;
  }

  private async _save(): Promise<void> {
    const hass = this.hass;
    if (!hass || this._saving || !this._selected || !this._label) return;
    const message: Record<string, unknown> = {
      type: ADD_LABEL,
      entity_id: this.entity,
      appointment: this._selected,
      label: this._label,
    };
    const note = this._note.trim();
    if (note) message["note"] = note;
    this._saving = true;
    this._error = "";
    try {
      await hass.callWS(message);
      this._saving = false;
      this.dispatchEvent(new CustomEvent("label-added", { bubbles: true, composed: true }));
      this._close();
    } catch (error) {
      this._saving = false;
      this._error = this._message(error, this.texts.label_errors["default"] ?? "");
    }
  }

  private _describe(appointment: Appointment): string {
    const texts = this.texts;
    const names: string[] = [];
    if (appointment.info_type !== null) names.push(typeLabel(texts, appointment.info_type, ""));
    for (const label of appointment.manual_labels) names.push(label.name);
    return names.filter(Boolean).join(", ");
  }

  protected override render(): TemplateResult {
    const texts = this.texts;
    const dialog = texts.dialog;
    const canSave = !this._saving && this._selected !== "" && this._label !== "";
    return html`<dialog
      aria-labelledby="title"
      @close=${() => {
        this._emitClosed();
      }}
      @cancel=${(event: Event) => {
        event.preventDefault();
        this._close();
      }}
    >
      <form
        @submit=${(event: Event) => {
          event.preventDefault();
          void this._save();
        }}
      >
        <header>
          <h2 id="title">${dialog.title}</h2>
          <button type="button" class="close" aria-label=${dialog.close} @click=${() => {
            this._close();
          }}>×</button>
        </header>

        <label class="field">
          <span>${dialog.date}</span>
          <input
            type="date"
            autofocus
            .value=${this._date}
            min=${this.min}
            max=${this.max}
            required
            @change=${(event: Event) => {
              this._date = (event.target as HTMLInputElement).value;
              void this._load(this._date);
            }}
          />
          ${this._date
            ? html`<small>${formatDay(this._date, this.language === "nl" ? "nl" : "en-GB")}</small>`
            : nothing}
        </label>

        <fieldset class="lessons" aria-busy=${this._loading ? "true" : "false"}>
          <legend>${dialog.lessons}</legend>
          ${this._renderLessons()}
        </fieldset>

        <label class="field">
          <span>${dialog.label}</span>
          <select
            required
            @change=${(event: Event) => {
              this._label = (event.target as HTMLSelectElement).value;
              this._error = "";
            }}
          >
            <option value="" ?selected=${this._label === ""}>${dialog.choose_label}</option>
            ${this.labels.map(
              (label) =>
                html`<option value=${label.id} ?selected=${this._label === label.id}>
                  ${label.name} (${texts.kind[label.kind]})
                </option>`,
            )}
          </select>
        </label>

        <label class="field">
          <span>${dialog.note}</span>
          <textarea
            rows="2"
            maxlength=${NOTE_MAX}
            .value=${this._note}
            @input=${(event: Event) => {
              this._note = (event.target as HTMLTextAreaElement).value;
            }}
          ></textarea>
          <small class="count">${format(dialog.note_count, { n: this._note.length })}</small>
        </label>

        ${this._error ? html`<p class="error" role="alert">${this._error}</p>` : nothing}

        <footer>
          <button type="button" class="secondary" @click=${() => {
            this._close();
          }}>${dialog.cancel}</button>
          <button type="submit" class="primary" ?disabled=${!canSave}>
            ${this._saving ? dialog.saving : dialog.save}
          </button>
        </footer>
      </form>
    </dialog>`;
  }

  private _renderLessons(): TemplateResult {
    const texts = this.texts;
    if (this._loading) return html`<p class="hint" role="status">${texts.dialog.lessons_loading}</p>`;
    if (this._loadError) return html`<p class="error" role="alert">${this._loadError}</p>`;
    if (this._appointments.length === 0) {
      return html`<p class="hint" role="status">${texts.dialog.no_lessons}</p>`;
    }
    return html`${this._appointments.map((appointment) => {
      const time = appointment.all_day ? texts.all_day : timeRange(appointment);
      const labels = this._describe(appointment);
      return html`<label class="lesson ${appointment.cancelled ? "cancelled" : ""}">
        <input
          type="radio"
          name="lesson"
          .value=${appointment.uid}
          .checked=${this._selected === appointment.uid}
          @change=${() => {
            this._selected = appointment.uid;
            this._error = "";
          }}
        />
        <span class="lesson-body">
          <span class="lesson-line">
            <strong>${appointment.subject}</strong>
            ${appointment.lesson_hour !== null
              ? html`<span class="meta">${format(texts.lesson_hour, { n: appointment.lesson_hour })}</span>`
              : nothing}
            ${time ? html`<span class="meta">${time}</span>` : nothing}
            ${appointment.cancelled ? html`<span class="badge">${texts.cancelled}</span>` : nothing}
          </span>
          ${labels ? html`<span class="lesson-labels">${labels}</span>` : nothing}
        </span>
      </label>`;
    })}`;
  }

  static override styles = css`
    :host {
      display: contents;
    }
    dialog {
      box-sizing: border-box;
      width: min(480px, calc(100vw - 32px));
      max-height: calc(100vh - 32px);
      max-height: calc(100dvh - 32px);
      overflow: auto;
      padding: 16px;
      border: none;
      border-radius: 12px;
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color, #212121);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    }
    dialog::backdrop {
      background: rgba(0, 0, 0, 0.5);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    h2 {
      margin: 0;
      font-size: 1.2em;
      font-weight: 500;
    }
    .close {
      min-width: 44px;
      min-height: 44px;
      border: none;
      background: none;
      color: inherit;
      font-size: 1.6em;
      line-height: 1;
      cursor: pointer;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 4px;
      margin: 12px 0;
      font-size: 0.9em;
      font-weight: 500;
    }
    .field small {
      font-weight: 400;
      color: var(--secondary-text-color);
    }
    input[type="date"],
    select,
    textarea {
      box-sizing: border-box;
      width: 100%;
      min-height: 44px;
      padding: 8px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      background: var(--secondary-background-color, transparent);
      color: var(--primary-text-color);
      font: inherit;
      font-weight: 400;
    }
    textarea {
      resize: vertical;
    }
    fieldset.lessons {
      margin: 12px 0;
      padding: 0;
      border: none;
      min-width: 0;
    }
    legend {
      padding: 0;
      margin-bottom: 4px;
      font-size: 0.9em;
      font-weight: 500;
    }
    .lesson {
      display: flex;
      gap: 10px;
      align-items: flex-start;
      min-height: 44px;
      padding: 8px;
      border: 1px solid var(--divider-color);
      border-radius: 8px;
      margin-bottom: 6px;
      cursor: pointer;
    }
    .lesson:has(input:checked) {
      border-color: var(--primary-color);
      background: color-mix(in srgb, var(--primary-color) 12%, transparent);
    }
    .lesson input {
      flex: none;
      width: 20px;
      height: 20px;
      margin: 2px 0 0;
      accent-color: var(--primary-color);
    }
    .lesson.cancelled strong {
      text-decoration: line-through;
    }
    .lesson-body {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }
    .lesson-line {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 2px 8px;
    }
    .meta,
    .lesson-labels {
      font-size: 0.85em;
      color: var(--secondary-text-color);
    }
    .badge {
      padding: 0 8px;
      border-radius: 10px;
      font-size: 0.75em;
      color: var(--error-color);
      border: 1px solid var(--error-color);
    }
    .hint {
      margin: 8px 0;
      color: var(--secondary-text-color);
    }
    .error {
      margin: 8px 0;
      color: var(--error-color);
    }
    footer {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 16px;
    }
    footer button {
      min-height: 44px;
      padding: 0 16px;
      border-radius: 8px;
      font: inherit;
      font-weight: 500;
      cursor: pointer;
    }
    .secondary {
      border: 1px solid var(--divider-color);
      background: none;
      color: var(--primary-text-color);
    }
    .primary {
      border: 1px solid var(--primary-color);
      background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .primary:disabled {
      opacity: 0.5;
      cursor: default;
    }
    input:focus-visible,
    select:focus-visible,
    textarea:focus-visible,
    button:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
  `;
}
