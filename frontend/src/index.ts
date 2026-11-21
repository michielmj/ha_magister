import { MagisterHomeworkCardEditor } from "./editor";
import { MagisterLabelDialog } from "./label-dialog";
import { MagisterHomeworkCard } from "./magister-homework-card";
import { MagisterTimerCard } from "./timer-card";
import { MagisterTimerCardEditor } from "./timer-card-editor";

declare global {
  interface Window {
    customCards?: {
      type: string;
      name: string;
      description: string;
      preview?: boolean;
      documentationURL?: string;
    }[];
  }
}

if (!customElements.get("magister-homework-card")) {
  customElements.define("magister-homework-card", MagisterHomeworkCard);
}
if (!customElements.get("magister-label-dialog")) {
  customElements.define("magister-label-dialog", MagisterLabelDialog);
}
if (!customElements.get("magister-homework-card-editor")) {
  customElements.define("magister-homework-card-editor", MagisterHomeworkCardEditor);
}

if (!customElements.get("magister-timer-card")) {
  customElements.define("magister-timer-card", MagisterTimerCard);
}
if (!customElements.get("magister-timer-card-editor")) {
  customElements.define("magister-timer-card-editor", MagisterTimerCardEditor);
}

window.customCards = window.customCards ?? [];
if (!window.customCards.some((card) => card.type === "magister-homework-card")) {
  window.customCards.push({
    type: "magister-homework-card",
    name: "Magister Homework planner",
    description:
      "Homework and tests of one child from Magister, with progress per item. / Huiswerk en toetsen van één kind uit Magister, met voortgang per onderdeel.",
    preview: true,
    documentationURL: "https://github.com/michielmj/ha_magister",
  });
}

if (!window.customCards.some((card) => card.type === "magister-timer-card")) {
  window.customCards.push({
    type: "magister-timer-card",
    name: "Magister Study timer",
    description:
      "The study timer of one child: countdown, pause, stop and progress. / De studietimer van één kind: aftellen, pauzeren, stoppen en voortgang.",
    preview: true,
    documentationURL: "https://github.com/michielmj/ha_magister",
  });
}

export { MagisterHomeworkCard, MagisterHomeworkCardEditor, MagisterTimerCard, MagisterTimerCardEditor };
