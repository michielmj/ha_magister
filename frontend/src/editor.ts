import { LitElement, html, nothing, type TemplateResult } from "lit";
import { DEFAULT_DAYS_AHEAD, MAX_DAYS_AHEAD } from "./logic";
import { textsFor, type Texts } from "./translations";
import type { CardConfig, Hass } from "./types";

export interface FormSchema {
  name: string;
  required?: boolean;
  selector: Record<string, unknown>;
}

/** The ha-form schema of the card editor. */
export function editorSchema(): FormSchema[] {
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { domain: "todo", integration: "magister" } },
    },
    { name: "title", selector: { text: {} } },
    { name: "show_completed", selector: { boolean: {} } },
    { name: "show_past", selector: { boolean: {} } },
    {
      name: "days_ahead",
      selector: { number: { min: 0, max: MAX_DAYS_AHEAD, step: 1, mode: "box" } },
    },
  ];
}

/** The values the form shows: the config with the card's defaults. */
export function formData(config: Partial<CardConfig>): Record<string, unknown> {
  return {
    entity: config.entity ?? "",
    title: config.title ?? "",
    show_completed: config.show_completed ?? false,
    show_past: config.show_past ?? false,
    days_ahead: config.days_ahead ?? DEFAULT_DAYS_AHEAD,
  };
}

/**
 * The config after a form change. Defaults and empty values are left out, so the YAML
 * stays short; the card type is kept.
 */
export function configFromForm(
  previous: Partial<CardConfig>,
  value: Record<string, unknown>,
): CardConfig {
  const config: CardConfig = { type: previous.type ?? "custom:magister-homework-card", entity: "" };
  if (typeof value["entity"] === "string") config.entity = value["entity"];
  if (typeof value["title"] === "string" && value["title"].trim() !== "") {
    config.title = value["title"];
  }
  if (value["show_completed"] === true) config.show_completed = true;
  if (value["show_past"] === true) config.show_past = true;
  const days = Number(value["days_ahead"]);
  if (
    value["days_ahead"] !== "" &&
    value["days_ahead"] !== undefined &&
    Number.isFinite(days) &&
    days >= 0 &&
    days !== DEFAULT_DAYS_AHEAD
  ) {
    config.days_ahead = Math.min(Math.floor(days), MAX_DAYS_AHEAD);
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
      .schema=${editorSchema()}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`;
  }
}
