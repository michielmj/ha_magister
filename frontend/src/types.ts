/** Shapes shared by the card, the editor and the logic (see docs/reference/homework-websocket.md). */

export type LabelKind = "homework" | "test";

/** A label option configured for the child (since 1.3.0). */
export interface LabelOption {
  id: string;
  name: string;
  kind: LabelKind;
}

export interface ManualLabel extends LabelOption {
  note: string;
}

/** One appointment of the add-label dialog (since 1.3.0). */
export interface Appointment {
  uid: string;
  /** Local ISO datetime with offset, or a date for all-day appointments. */
  start: string;
  end: string;
  all_day: boolean;
  lesson_hour: number | null;
  subject: string;
  cancelled: boolean;
  info_type: number | null;
  manual_labels: ManualLabel[];
}

export interface HomeworkItem {
  uid: string;
  due: string;
  /** Local due date, YYYY-MM-DD. Items are grouped by this. */
  date: string;
  all_day: boolean;
  lesson_hour: number | null;
  subject: string;
  /** 1 Huiswerk, 2 Proefwerk, 3 Tentamen, 4 SO, 5 MO; null when only manual labels put it in the planner. */
  info_type: number | null;
  /** The Dutch label; only a fallback for unknown info types. */
  label: string | null;
  /** Labels added in the card (since 1.3.0); only these can be removed. */
  manual_labels: ManualLabel[];
  is_test: boolean;
  text: string;
  cancelled: boolean;
  has_attachments: boolean;
  /** 0-100 */
  progress: number;
  completed: boolean;
  /** The value that unticking restores (0-99). */
  last_partial: number;
}

/** The value of one progress sensor (since 1.2.0); null when that sensor is unavailable. */
export interface PeriodProgress {
  /** 0-100 */
  value: number;
  items: number;
  completed: number;
}

export type ProgressPeriod = "next_day" | "week" | "next_week";

export type ProgressMap = Record<ProgressPeriod, PeriodProgress | null>;

export interface HomeworkPayload {
  available: boolean;
  items: HomeworkItem[];
  /** The label options of this child (since 1.3.0); absent or empty: no adding. */
  labels?: LabelOption[];
  /** Absent when the backend predates 1.2.0. */
  progress?: ProgressMap;
}

export interface SetProgressResult {
  progress: number;
  completed: boolean;
}

export type CardLanguage = "auto" | "nl" | "en";

export interface CardConfig {
  type: string;
  entity: string;
  show_completed?: boolean;
  show_past?: boolean;
  days_ahead?: number;
  show_progress_tomorrow?: boolean;
  show_progress_week?: boolean;
  show_progress_next_week?: boolean;
  title?: string;
  language?: CardLanguage;
  /** Generated once by the visual editor; keeps the remembered switches per card. */
  card_id?: string;
}

export type Unsubscribe = () => Promise<void> | void;

/** The part of home-assistant-js-websocket's Connection that the card uses. */
export interface HassConnection {
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-parameters -- same signature as Home Assistant's
  subscribeMessage<T>(
    callback: (message: T) => void,
    subscribeMessage: Record<string, unknown>,
    options?: { resubscribe?: boolean },
  ): Promise<Unsubscribe>;
  /** False while the socket is down (js-websocket). */
  connected?: boolean;
  addEventListener?(type: string, listener: () => void): void;
  removeEventListener?(type: string, listener: () => void): void;
}

/** The part of the Home Assistant frontend object that the card uses. */
export interface Hass {
  language?: string;
  locale?: { language?: string };
  config?: { time_zone?: string };
  connection: HassConnection;
  entities?: Record<string, { platform?: string } | undefined>;
  callWS<T>(message: Record<string, unknown>): Promise<T>;
}

export interface WsError {
  code?: string;
  message?: string;
}
