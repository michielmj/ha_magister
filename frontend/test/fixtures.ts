import type { HomeworkItem } from "../src/types";

/** Placeholder items (no real data). Today in the tests is 2026-11-13 (a Friday). */
export function item(overrides: Partial<HomeworkItem> = {}): HomeworkItem {
  return {
    uid: "school.example.net:1:1",
    due: "2026-11-13T10:00:00+01:00",
    date: "2026-11-13",
    all_day: false,
    lesson_hour: 2,
    subject: "Wiskunde",
    info_type: 1,
    manual_labels: [],
    label: "Huiswerk",
    is_test: false,
    text: "Maak opdracht 1 t/m 5",
    cancelled: false,
    has_attachments: false,
    progress: 0,
    completed: false,
    last_partial: 0,
    ...overrides,
  };
}

export const TODAY = "2026-11-13";
