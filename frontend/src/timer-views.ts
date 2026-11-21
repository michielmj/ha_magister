import { css, html, nothing, type TemplateResult } from "lit";
import { live } from "lit/directives/live.js";
import { notifyState, setEnabled, setSound } from "./notifications";
import { STEPS, formatMinutes } from "./logic";
import { EXTRA_MAX, PREWARN_MAX, formatCountdown } from "./timer";
import type { TimerController, TimerView } from "./timer-controller";
import { format, type Texts } from "./translations";

/** The pieces both cards render: buttons, the panel "Hoe ver ben je?", the settings panel, the live region. */
export interface TimerContext {
  controller: TimerController;
  texts: Texts;
  language: "nl" | "en";
  /** The buttons work (connected, data available). */
  enabled: boolean;
}

const ICONS: Record<string, string> = {
  play: "M8,5.14V19.14L19,12.14Z",
  pause: "M14,19H18V5H14M6,19H10V5H6V19Z",
  stop: "M18,18H6V6H18V18Z",
  done: "M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z",
};

const icon = (name: string): TemplateResult =>
  html`<svg class="glyph" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d=${ICONS[name] ?? ""}></path></svg>`;

export type Where = "row" | "bar" | "card";

const stateText = (texts: Texts, view: TimerView): string => texts.timer[view.state];

/** The live region: the pre-warning and the end are announced here, never every second. */
export function renderLive(context: TimerContext): TemplateResult {
  return html`<div class="sr-only timer-live" role="status" aria-live="polite" aria-atomic="true">${context.controller.announcement}</div>`;
}

/** The countdown, readable for a screen reader without announcing each second. */
export function renderCountdown(
  context: TimerContext,
  view: TimerView,
  extraClass = "",
): TemplateResult {
  const { texts } = context;
  return html`<span class="countdown ${view.state} ${extraClass}" role="timer" aria-live="off"
    ><span class="sr-only">${format(texts.timer.countdown_aria, {
      title: view.timer.title,
      state: stateText(texts, view),
    })}: </span
    >${formatCountdown(view.remaining)}</span
  >`;
}

/** The ▶ start button of a subtask row. */
export function renderStartButton(
  context: TimerContext,
  uid: string,
  title: string,
  minutes: number,
): TemplateResult {
  const { texts, controller } = context;
  const time = formatMinutes(minutes, context.language);
  return html`<button
    type="button"
    class="icon-btn timer-start"
    data-timer-start=${uid}
    ?disabled=${!context.enabled || controller.disabled}
    title=${texts.timer.start}
    aria-label=${format(texts.timer.start_aria, { title, time })}
    @click=${() => {
      controller.start(uid, "row");
    }}
  >${icon("play")}</button>`;
}

/** The buttons of the running, paused or finished timer, in the three places it is shown. */
export function renderActions(context: TimerContext, view: TimerView, where: Where): TemplateResult {
  const { texts, controller } = context;
  const off = !context.enabled || controller.disabled;
  const uid = view.timer.subtask;
  const title = view.timer.title;
  const big = where === "card";
  const button = (
    act: string,
    glyph: string,
    label: string,
    aria: string,
    onClick: () => void,
    extra = "",
    alwaysLabel = false,
  ): TemplateResult => html`<button
    type="button"
    class="timer-btn ${extra} ${big ? "big" : ""}"
    data-timer-act=${act}
    data-timer-uid=${uid}
    data-timer-where=${where}
    ?disabled=${off}
    title=${label}
    aria-label=${aria}
    @click=${onClick}
  >${glyph ? icon(glyph) : nothing}${big || alwaysLabel || !glyph
    ? html`<span class="label">${label}</span>`
    : nothing}</button>`;
  if (view.state === "finished") {
    const extra = controller.extraMinutes(view);
    return html`<span class="timer-actions" role="group" aria-label=${format(texts.timer.finished_group, { title })}>
      ${button("done", "done", texts.timer.done, format(texts.timer.done_aria, { title }), () => {
        controller.done();
      }, "primary", true)}
      ${extra
        ? button(
            "extend",
            "",
            format(texts.timer.extra, { n: extra }),
            format(texts.timer.extra_aria, { n: extra, title }),
            () => {
              controller.extend(where);
            },
            "",
            true,
          )
        : nothing}
      ${button("not_yet", "", texts.timer.not_yet, format(texts.timer.not_yet_aria, { title }), () => {
        controller.openPanel();
      }, "", true)}
    </span>`;
  }
  return html`<span class="timer-actions">
    ${view.state === "running"
      ? button("pause", "pause", texts.timer.pause, format(texts.timer.pause_aria, { title }), () => {
          controller.pause(where);
        })
      : button("resume", "play", texts.timer.resume, format(texts.timer.resume_aria, { title }), () => {
          controller.resume(where);
        })}
    ${button("stop", "stop", texts.timer.stop, format(texts.timer.stop_aria, { title }), () => {
      controller.openPanel();
    })}
  </span>`;
}

/** The inline question "Hoe ver ben je?" that Stop and "Nog niet" open. */
export function renderPanel(context: TimerContext): TemplateResult | typeof nothing {
  const { controller, texts } = context;
  const panel = controller.panel;
  const view = controller.view();
  if (!panel || !view) return nothing;
  const off = !context.enabled || controller.disabled;
  const title = view.timer.title;
  const move = (event: KeyboardEvent): void => {
    const index = STEPS.indexOf(panel.selected as (typeof STEPS)[number]);
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
    const value = STEPS[next];
    if (value !== undefined) controller.selectStep(value);
  };
  return html`<section
    class="timer-panel"
    role="group"
    aria-labelledby="timer-panel-title"
    @keydown=${(event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        controller.closePanel();
      }
    }}
  >
    <h4 id="timer-panel-title" class="timer-panel-title">${texts.timer.panel_title}</h4>
    <p class="meta timer-panel-for">${title}</p>
    <div class="steps" role="radiogroup" aria-label=${format(texts.timer.panel_aria, { title })}>
      ${STEPS.map(
        (step) => html`<button
          type="button"
          role="radio"
          class="step ${step === panel.selected ? "selected" : ""}"
          aria-checked=${step === panel.selected ? "true" : "false"}
          aria-label=${format(texts.percent, { n: step })}
          tabindex=${step === panel.selected ? 0 : -1}
          ?disabled=${off}
          @click=${() => {
            controller.selectStep(step);
          }}
          @keydown=${move}
        >${step}</button>`,
      )}
    </div>
    <div class="timer-panel-actions">
      <button type="button" class="cancel" @click=${() => {
        controller.closePanel();
      }}>${texts.timer.panel_cancel}</button>
      <button type="button" class="discard" ?disabled=${off} @click=${() => {
        controller.stop(false);
      }}>${texts.timer.panel_discard}</button>
      <button type="button" class="primary" ?disabled=${off} @click=${() => {
        controller.stop(true);
      }}>${texts.timer.panel_save}</button>
    </div>
  </section>`;
}

/** "Er loopt al een timer ... Vervangen?" under the row that was asked to start. */
export function renderReplaceConfirm(context: TimerContext, uid: string, title: string): TemplateResult | typeof nothing {
  const { controller, texts } = context;
  const view = controller.view();
  if (controller.confirmUid !== uid || !view) return nothing;
  const question = format(texts.timer.confirm_replace, { title: view.timer.title });
  return html`<div
    class="timer-confirm"
    role="group"
    aria-label=${question}
    @keydown=${(event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        controller.cancelConfirm(uid);
      }
    }}
  >
    <span>${question}</span>
    <button type="button" class="cancel" data-timer-cancel aria-label=${format(texts.timer.confirm_no_aria, { title })} @click=${() => {
      controller.cancelConfirm(uid);
    }}>${texts.timer.confirm_no}</button>
    <button type="button" class="primary" data-timer-replace ?disabled=${!context.enabled || controller.disabled} @click=${() => {
      controller.start(uid, "row", true);
    }}>${texts.timer.confirm_yes}</button>
  </div>`;
}

/** The ⚙ button that opens the settings panel. */
export function renderSettingsButton(context: TimerContext): TemplateResult {
  const { controller, texts } = context;
  return html`<button
    type="button"
    class="timer-settings-btn"
    data-timer-settings-button
    aria-expanded=${controller.settingsOpen ? "true" : "false"}
    title=${texts.timer.settings}
    aria-label=${texts.timer.settings}
    @click=${() => {
      if (controller.settingsOpen) controller.closeSettings();
      else controller.openSettings();
    }}
  ><span aria-hidden="true">⚙</span></button>`;
}

const range = (max: number): number[] => Array.from({ length: max }, (_, index) => index + 1);

/** "Meldingen in deze browser" and "Geluid": per browser, so also for a viewer who may not control the timer. */
export function renderNotifySettings(context: TimerContext): TemplateResult {
  const { texts } = context;
  const state = notifyState();
  const text = texts.timer;
  let body: TemplateResult;
  if (state.availability !== "ok") {
    const reason = {
      app: text.notify_app,
      insecure: text.notify_insecure,
      unsupported: text.notify_unsupported,
    }[state.availability];
    body = html`<p class="meta notify-unavailable">${reason}</p>`;
  } else {
    body = html`<label class="notify-row">
        <input
          type="checkbox"
          id="timer-notify"
          .checked=${live(state.active)}
          @change=${(event: Event) => {
            void setEnabled((event.target as HTMLInputElement).checked, text.notify_confirm);
          }}
        />
        <span>${text.notify_enable}</span>
      </label>
      ${state.permission === "denied"
        ? html`<p class="timer-error notify-denied" role="status">${text.notify_denied}</p>
            <p class="meta">${text.notify_denied_hint}</p>`
        : nothing}
      ${state.active
        ? html`<label class="notify-row">
            <input
              type="checkbox"
              id="timer-notify-sound"
              .checked=${live(state.sound)}
              @change=${(event: Event) => {
                setSound((event.target as HTMLInputElement).checked);
              }}
            />
            <span>${text.notify_sound}</span>
          </label>`
        : nothing}
      <p class="meta">${text.notify_hint}</p>`;
  }
  return html`<div class="timer-notify" role="group" aria-label=${text.notify_title}>${body}</div>`;
}

/** The small "Meldingen" button of the timer card, which opens that panel. */
export function renderNotifyButton(context: TimerContext, open: boolean, toggle: () => void): TemplateResult {
  const { texts } = context;
  return html`<div class="notify-bar">
    <button
      type="button"
      class="notify-btn"
      data-notify-button
      aria-expanded=${open ? "true" : "false"}
      @click=${toggle}
    ><span aria-hidden="true">⚙</span> ${texts.timer.notify_title}</button>
    ${open
      ? html`<div
          class="timer-settings notify-panel"
          tabindex="-1"
          @keydown=${(event: KeyboardEvent) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              toggle();
            }
          }}
        >${renderNotifySettings(context)}</div>`
      : nothing}
  </div>`;
}

/** The pre-warning and the extra minutes: off, or a number of minutes. */
export function renderSettings(context: TimerContext): TemplateResult | typeof nothing {
  const { controller, texts } = context;
  if (!controller.settingsOpen) return nothing;
  const form = controller.settingsForm;
  const off = !context.enabled || controller.disabled;
  const select = (
    id: string,
    label: string,
    max: number,
    value: string,
    set: (value: string) => void,
  ): TemplateResult => html`<label>
    <span>${label}</span>
    <select
      id=${id}
      ?disabled=${off}
      aria-invalid=${form.error ? "true" : "false"}
      aria-describedby=${form.error ? "timer-settings-error" : nothing}
      @change=${(event: Event) => {
        set((event.target as HTMLSelectElement).value);
      }}
    >
      <option value="" ?selected=${value === ""}>${texts.timer.off}</option>
      ${range(max).map(
        (n) =>
          html`<option value=${String(n)} ?selected=${value === String(n)}>${format(texts.timer.minutes_option, { n })}</option>`,
      )}
    </select>
  </label>`;
  return html`<form
    class="timer-settings"
    role="group"
    aria-label=${texts.timer.settings_title}
    novalidate
    @submit=${(event: Event) => {
      event.preventDefault();
      void controller.saveSettings();
    }}
    @keydown=${(event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        controller.closeSettings();
      }
    }}
  >
    <h4 class="timer-panel-title">${texts.timer.settings_title}</h4>
    ${select("timer-prewarn", texts.timer.prewarn, PREWARN_MAX, form.prewarn, (value) => {
      controller.patchSettings({ prewarn: value });
    })}
    ${select("timer-extra", texts.timer.extra_minutes, EXTRA_MAX, form.extra, (value) => {
      controller.patchSettings({ extra: value });
    })}
    <p class="meta">${texts.timer.settings_hint}</p>
    ${form.error
      ? html`<p class="timer-error" id="timer-settings-error" role="alert" tabindex="-1">${form.error}</p>`
      : nothing}
    <div class="timer-panel-actions">
      <button type="button" class="cancel" @click=${() => {
        controller.closeSettings();
      }}>${texts.timer.cancel}</button>
      <button type="submit" class="primary" ?disabled=${off}>${texts.timer.save}</button>
    </div>
  </form>
  <div
    class="timer-settings notify-panel"
    @keydown=${(event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        controller.closeSettings();
      }
    }}
  >${renderNotifySettings(context)}</div>`;
}

/** Everything the timer buttons and panels need, in one stylesheet shared by both cards. */
export const timerStyles = css`
  :host {
    --timer-color: var(--primary-color, #03a9f4);
    --timer-warn: var(--warning-color, #ffa600);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
  .glyph {
    width: 18px;
    height: 18px;
    fill: currentColor;
  }
  .countdown {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .countdown.paused {
    color: var(--secondary-text-color);
  }
  .timer-actions {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
  .timer-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-width: 36px;
    min-height: 36px;
    padding: 0 12px;
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 0.85em;
    cursor: pointer;
  }
  .timer-btn.primary {
    border-color: var(--timer-color);
    background: var(--timer-color);
    color: var(--text-primary-color, #fff);
  }
  .timer-btn.big {
    min-height: 56px;
    min-width: 56px;
    padding: 0 22px;
    border-radius: 28px;
    font-size: 1.1em;
  }
  .timer-btn:disabled,
  .timer-start:disabled,
  .timer-panel button:disabled,
  .timer-settings button:disabled,
  .timer-confirm button:disabled {
    cursor: default;
    opacity: 0.6;
  }
  .timer-btn:focus-visible,
  .timer-start:focus-visible,
  .timer-settings-btn:focus-visible,
  .timer-panel button:focus-visible,
  .timer-settings button:focus-visible,
  .timer-settings select:focus-visible,
  .timer-confirm button:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .timer-start {
    color: var(--timer-color);
  }
  .timer-notify {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding-top: 6px;
    border-top: 1px solid var(--divider-color);
  }
  .notify-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 36px;
    cursor: pointer;
  }
  .notify-row input {
    width: 20px;
    height: 20px;
    margin: 0;
    accent-color: var(--primary-color);
  }
  .notify-row input:focus-visible,
  .notify-btn:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .notify-bar {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    margin-top: 12px;
  }
  .notify-bar .notify-panel {
    align-self: stretch;
  }
  .notify-btn {
    min-height: 36px;
    padding: 0 12px;
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    background: transparent;
    color: var(--secondary-text-color);
    font: inherit;
    font-size: 0.9em;
    cursor: pointer;
  }
  .timer-settings-btn {
    min-width: 36px;
    min-height: 36px;
    padding: 0;
    border: 1px solid var(--divider-color);
    border-radius: 18px;
    background: transparent;
    color: var(--secondary-text-color);
    font: inherit;
    font-size: 1.1em;
    cursor: pointer;
  }
  .timer-panel,
  .timer-settings,
  .timer-confirm {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 8px 0;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--timer-color) 50%, transparent);
    background: color-mix(in srgb, var(--timer-color) 8%, transparent);
    font-size: 0.9em;
  }
  .timer-confirm {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    margin: 6px 0 0;
    padding: 6px 8px;
  }
  .timer-panel-title {
    margin: 0;
    font-size: 1.05em;
    font-weight: 600;
    color: var(--primary-text-color);
  }
  .timer-panel-for {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .steps {
    display: flex;
    border: 1px solid var(--divider-color);
    border-radius: 8px;
    overflow: hidden;
    max-width: 320px;
  }
  .step {
    flex: 1;
    min-height: 44px;
    padding: 0;
    border: none;
    border-left: 1px solid var(--divider-color);
    background: transparent;
    color: var(--secondary-text-color);
    font: inherit;
    cursor: pointer;
  }
  .step:first-child {
    border-left: none;
  }
  .step.selected {
    background: var(--timer-color);
    color: var(--text-primary-color, #fff);
    font-weight: 700;
  }
  .timer-panel-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: flex-end;
  }
  .timer-panel-actions button,
  .timer-confirm button {
    min-height: 40px;
    padding: 0 14px;
    border-radius: 20px;
    border: 1px solid var(--divider-color);
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 0.9em;
    cursor: pointer;
  }
  .timer-panel .primary,
  .timer-settings .primary,
  .timer-confirm .primary {
    border-color: var(--timer-color);
    background: var(--timer-color);
    color: var(--text-primary-color, #fff);
  }
  .timer-settings label {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 0.85em;
    color: var(--secondary-text-color);
  }
  .timer-settings select {
    min-height: 40px;
    max-width: 220px;
    padding: 0 8px;
    border: 1px solid var(--divider-color);
    border-radius: 6px;
    background: transparent;
    color: var(--primary-text-color);
    font: inherit;
    font-size: 1.05em;
  }
  .timer-error {
    margin: 0;
    color: var(--error-color);
  }
  .timer-track {
    height: 4px;
    margin-top: 6px;
    border-radius: 2px;
    overflow: hidden;
    background: var(--divider-color);
  }
  .timer-fill {
    height: 100%;
    background: var(--timer-color);
  }
  @media (pointer: coarse) {
    .timer-btn,
    .icon-btn.timer-start,
    .icon-btn.timer-settings-btn,
    .timer-start,
    .timer-settings-btn {
      min-height: 44px;
      min-width: 44px;
    }
  }
`;
