import { LitElement, html, nothing, type TemplateResult } from "lit";
import type { FormSchema } from "./editor";
import { textsFor, type Texts } from "./translations";
import type { Hass, TimerCardConfig } from "./types";

/** The ha-form schema of the timer card editor. */
export function timerEditorSchema(): FormSchema[] {
  return [
    {
      name: "entity",
      required: true,
      selector: { entity: { filter: { domain: "todo", integration: "magister" } } },
    },
    { name: "title", selector: { text: {} } },
    { name: "show_when_idle", selector: { boolean: {} } },
  ];
}

/** The values the form shows: the config with the card's defaults. */
export function timerFormData(config: Partial<TimerCardConfig>): Record<string, unknown> {
  return {
    entity: config.entity ?? "",
    title: config.title ?? "",
    show_when_idle: config.show_when_idle !== false,
  };
}

/** The config after a form change: defaults and empty values are removed, other keys are kept. */
export function timerConfigFromForm(
  previous: Partial<TimerCardConfig>,
  value: Record<string, unknown>,
): TimerCardConfig {
  const config = {
    ...previous,
    type: previous.type ?? "custom:magister-timer-card",
    entity: typeof value["entity"] === "string" ? value["entity"] : (previous.entity ?? ""),
  };
  const title = value["title"];
  if (typeof title === "string" && title.trim() !== "") config.title = title;
  else delete config.title;
  if (value["show_when_idle"] === false) config.show_when_idle = false;
  else delete config.show_when_idle;
  return config;
}

export class MagisterTimerCardEditor extends LitElement {
  static override properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  declare hass: Hass | undefined;
  declare _config: Partial<TimerCardConfig> | undefined;

  setConfig(config: Partial<TimerCardConfig>): void {
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
    const config = timerConfigFromForm(this._config, event.detail.value);
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
    );
  };

  protected override render(): TemplateResult | typeof nothing {
    if (!this._config) return nothing;
    return html`<ha-form
      .hass=${this.hass}
      .data=${timerFormData(this._config)}
      .schema=${timerEditorSchema()}
      .computeLabel=${this._computeLabel}
      @value-changed=${this._valueChanged}
    ></ha-form>`;
  }
}
