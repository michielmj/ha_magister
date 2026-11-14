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
  override?: ItemOverride | null;
}

/** An override of the Magister label (since 1.4.0): replaced by a label option, or disabled. */
export type ItemOverride =
  | { mode: "replace"; label: LabelOption }
  | { mode: "disable" };

/** A subtask of an item (since 1.5.0). */
export interface Subtask {
  /** `<item uid>:sub:<id>` */
  uid: string;
  title: string;
  /** Planned local date, YYYY-MM-DD. */
  planned: string;
  /** Current local date: subtasks are grouped by this. */
  date: string;
  /** Not done and the item date is before today. */
  overdue: boolean;
  /** 0-100 */
  progress: number;
  completed: boolean;
  /** The value that unticking restores (0-99). */
  last_partial: number;
  /** Since 1.6.0: who created the subtask ("parent" since 1.7.0). A missing field counts as "user". */
  created_by?: "user" | "ai" | "parent";
  /** Since 1.7.0: the estimated time in minutes (5-240 in steps of 5); null or absent when unknown. */
  minutes?: number | null;
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
  /** Since 1.4.0: the override of the Magister label, null when there is none. */
  override?: ItemOverride | null;
  /** Since 1.4.0: no active labels left; the item counts as completed with weight 0. */
  disabled?: boolean;
  /** Any active label of kind test (follows overrides). */
  is_test: boolean;
  text: string;
  cancelled: boolean;
  has_attachments: boolean;
  /** 0-100 */
  progress: number;
  /** progress >= 100, or the item is disabled (since 1.4.0). */
  completed: boolean;
  /** The value that unticking restores (0-99). */
  last_partial: number;
  /** Since 1.5.0: the item has subtasks; its progress is then derived (the mean) and read-only. */
  derived?: boolean;
  /** Since 1.5.0: in creation order; empty (or absent) when none. */
  subtasks?: Subtask[];
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
  /** Since 1.7.0: the child's daily maximum of study minutes per school day; absent on older backends. */
  daily_max_minutes?: number;
}

export interface SetProgressResult {
  progress: number;
  completed: boolean;
}

/** The result of add_subtask, update_subtask and delete_subtask: the updated parent item. */
export type SubtaskResult = HomeworkItem;

export interface SetOverrideResult {
  /** Null when the appointment is not in the planner any more. */
  item: HomeworkItem | null;
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
