import { LitElement, html, nothing, type TemplateResult } from "lit";
import { DEFAULT_DAYS_AHEAD, MAX_DAYS_AHEAD, PROGRESS_PERIODS, generateCardId } from "./logic";
import { textsFor, type Texts } from "./translations";
import type { CardConfig, Hass } from "./types";

export interface FormSchema {
  name: string;
  required?: boolean;
  selector: Record<string, unknown>;
}

/** The ha-form schema of the card editor. */
export function editorSchema(texts: Texts = textsFor("en")): FormSchema[] {
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { domain: "todo", integration: "magister" } } },
    },
    { name: "title", selector: { text: {} } },
    {
      name: "language",
      selector: {
        select: {
          mode: "dropdown",
          options: [
            { value: "auto", label: texts.editor.language_auto },
            { value: "nl", label: "Nederlands" },
            { value: "en", label: "English" },
          ],
        },
      },
    },
    { name: "show_completed", selector: { boolean: {} } },
    { name: "show_past", selector: { boolean: {} } },
    {
      name: "days_ahead",
      selector: { number: { min: 0, max: MAX_DAYS_AHEAD, step: 1, mode: "box" } },
    },
    ...PROGRESS_PERIODS.map(({ option }) => ({ name: option, selector: { boolean: {} } })),
  ];
}

/** The values the form shows: the config with the card's defaults. */
export function formData(config: Partial<CardConfig>): Record<string, unknown> {
  return {
    entity: config.entity ?? "",
    title: config.title ?? "",
    language: config.language ?? "auto",
    show_completed: config.show_completed ?? false,
    show_past: config.show_past ?? false,
    days_ahead: config.days_ahead ?? DEFAULT_DAYS_AHEAD,
    show_progress_tomorrow: config.show_progress_tomorrow ?? false,
    show_progress_week: config.show_progress_week ?? false,
    show_progress_next_week: config.show_progress_next_week ?? false,
  };
}

/**
 * The config after a form change. Only the managed keys change (defaults and empty
 * values are removed, so the YAML stays short); every other key (grid_options,
 * visibility, view_layout, card_mod, ...) is kept.
 */
export function configFromForm(
  previous: Partial<CardConfig>,
  value: Record<string, unknown>,
): CardConfig {
  const config = {
    ...previous,
    type: previous.type ?? "custom:magister-homework-card",
    entity: typeof value["entity"] === "string" ? value["entity"] : (previous.entity ?? ""),
  };
  const title = value["title"];
  if (typeof title === "string" && title.trim() !== "") config.title = title;
  else delete config.title;
  const language = value["language"];
  if (language === "nl" || language === "en") config.language = language;
  else delete config.language;
  if (value["show_completed"] === true) config.show_completed = true;
  else delete config.show_completed;
  if (value["show_past"] === true) config.show_past = true;
  else delete config.show_past;
  const toggles: Record<string, unknown> = config;
  for (const { option } of PROGRESS_PERIODS) {
    if (value[option] === true) toggles[option] = true;
    // eslint-disable-next-line @typescript-eslint/no-dynamic-delete -- the three known toggle keys
    else delete toggles[option];
  }
  const raw = value["days_ahead"];
  const days = raw === "" || raw === undefined || raw === null ? Number.NaN : Number(raw);
  if (Number.isFinite(days) && days >= 0 && days !== DEFAULT_DAYS_AHEAD) {
    config.days_ahead = Math.min(Math.floor(days), MAX_DAYS_AHEAD);
  } else {
    delete config.days_ahead;
  }
  return config;
}

export class MagisterHomeworkCardEditor extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  declare hass: Hass | undefined;
  declare _config: Partial<CardConfig> | undefined;

  setConfig(config: Partial<CardConfig>): void {
    this._config = config;
  }

  private _texts(): Texts {
    return textsFor(this.hass?.locale?.language ?? this.hass?.language);
  }

  private readonly _computeLabel = (schema: FormSchema): string => {
    const labels = this._texts().editor as Record<string, string>;
    return labels[schema.name] ?? schema.name;
  };

  private readonly _valueChanged = (
    event: CustomEvent<{ value: Record<string, unknown> }>,
  ): void => {
    event.stopPropagation();
    if (!this._config) return;
    const config = configFromForm(this._config, event.detail.value);
    // A stable id of this card, made once: it keeps the card's remembered switches apart.
    config.card_id ??= generateCardId();
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
    );
  };

  protected override render(): TemplateResult | typeof nothing {
    if (!this._config) return nothing;
    return html`<ha-form
      .hass=${this.hass}
      .data=${formData(this._config)}
      .schema=${editorSchema(this._texts())}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`;
  }
}
