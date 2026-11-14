import { vi } from "vitest";
import "../src/index";
import type { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { Hass, HomeworkItem, HomeworkPayload, LabelOption, ManualLabel } from "../src/types";

export const ENTITY = "todo.kind_myschool_homework";

export class FakeConnection {
  callback: ((payload: HomeworkPayload) => void) | undefined;
  private readonly listeners = new Map<string, Set<() => void>>();

  subscribeMessage = (callback: (payload: HomeworkPayload) => void): Promise<() => void> => {
    this.callback = callback;
    return Promise.resolve(vi.fn());
  };
  addEventListener = (type: string, listener: () => void): void => {
    const set = this.listeners.get(type) ?? new Set();
    set.add(listener);
    this.listeners.set(type, set);
  };
  removeEventListener = (type: string, listener: () => void): void => {
    this.listeners.get(type)?.delete(listener);
  };
  emit(type: string): void {
    [...(this.listeners.get(type) ?? [])].forEach((listener) => {
      listener();
    });
  }
  push(payload: HomeworkPayload): void {
    this.callback?.(payload);
  }
}

export function makeHass(
  connection: FakeConnection,
  callWS: unknown = vi.fn(),
  language = "en",
): Hass {
  return {
    language,
    config: { time_zone: "Europe/Amsterdam" },
    connection: connection as unknown as Hass["connection"],
    callWS: callWS as Hass["callWS"],
  };
}

export async function flush(card: MagisterHomeworkCard): Promise<void> {
  for (let round = 0; round < 4; round++) {
    await Promise.resolve();
    await card.updateComplete;
  }
}

export async function mount(
  config: Record<string, unknown>,
  callWS: unknown = vi.fn(),
  language = "en",
): Promise<{ card: MagisterHomeworkCard; connection: FakeConnection }> {
  const connection = new FakeConnection();
  const card = document.createElement("magister-homework-card") as MagisterHomeworkCard;
  card.setConfig({ type: "custom:magister-homework-card", entity: ENTITY, ...config });
  card.hass = makeHass(connection, callWS, language);
  document.body.append(card);
  await flush(card);
  return { card, connection };
}

export const root = (card: MagisterHomeworkCard): ShadowRoot => {
  if (!card.shadowRoot) throw new Error("no shadow root");
  return card.shadowRoot;
};

export const LABELS: LabelOption[] = [
  { id: "l1", name: "Huiswerk", kind: "homework" },
  { id: "l2", name: "Toetsweek", kind: "test" },
];

export function manual(overrides: Partial<ManualLabel> = {}): ManualLabel {
  return { id: "l2", name: "Toetsweek", kind: "test", note: "", ...overrides };
}

export function payload(
  items: HomeworkItem[],
  options: { available?: boolean; labels?: LabelOption[] } = {},
): HomeworkPayload {
  return {
    available: options.available ?? true,
    items,
    ...(options.labels ? { labels: options.labels } : {}),
  };
}

/** A WS error like the ones Home Assistant rejects with (an object with a code). */
export function wsError(code: string): Error & { code: string } {
  return Object.assign(new Error(code), { code });
}
