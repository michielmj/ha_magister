# M8 — Replace or disable Magister labels (release 1.4.0)

| | |
|---|---|
| Status | **Approved by PM (2026-11-14)**, via the survey answers below |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M5–M7 · `docs/reference/homework-websocket.md` (binding, updated for 1.4.0) |

## Background
Teachers sometimes put "Proefwerk" on a lesson that only prepares for a test. The PM wants to correct such
Magister labels per lesson, without touching Magister.

## PM decisions (2026-11-14)
| # | Decision |
|---|---|
| 1 | A Magister label on a lesson can be **replaced** with one of the child's configured label options, or **disabled**. It can always be **restored**. |
| 2 | **Replaced:** the card shows the original chip **struck through**, followed by the replacement label. Weights, the test highlight and the sensors' `tests` count follow the **replacement**. |
| 3 | **Disabled:** the chip is struck through and the item is treated as **completed**: it is shown with the completed homework, does not count in the to-do count, has **weight 0**, and the bars and sensors ignore it. The stored progress is kept, and after restoring the item is as before. |
| 4 | **Calendar title:** a replaced label is shown as `[Proefwerk→Huiswerk]`. A disabled Magister label is **not** shown. Manual labels follow as now. |
| 5 | A disabled Magister label on a lesson that **also has active manual labels**: the item stays **active**, and its weight comes from the active labels. |
| 6 | **Weight rule (general):** an item's weight = the **maximum of the weights of its active labels** × the subject weight. The active labels are the effective Magister label (replacement, or the original when not overridden; none when disabled) plus the manual labels. With no active labels, the item counts as disabled (weight 0, shown as completed). |
| 7 | **HA's own to-do list:** a disabled item shows as **completed**. Restoring brings back its real status. |

## Design
- **Storage:** per appointment uid in the progress store, a new field
  `override: {"mode": "replace", "label": <label option id>} | {"mode": "disable"} | absent`.
  - The store moves to minor version 3, keeping major 1, so downgrades stay readable; the migration adds nothing.
  - Overrides are pruned with the same rules as progress and labels.
  - A replacement pointing to a label option that was later deleted falls back to the original Magister label.
    Deleting a label option that is used as a replacement is **refused** (same "in use" rule as manual labels).
- **Effective state** (one pure function in `api/homework.py`, used by the sensors, the payload, the to-do entity
  and the calendar):
  - `effective_label`: the original label, the replacement option, or none;
  - `active_labels`: the effective label plus the manual labels;
  - `disabled`: no active labels and an override of mode disable;
  - `is_test`: any active label of kind test;
  - `weight`: max(active label weights) × subject weight, or 0 when disabled.
- **Completion:**
  - `completed` (payload and to-do status) = `progress >= 100` **or** `disabled`.
  - `progress` keeps the stored value.
  - The to-do count excludes disabled items.
  - Ticking or unticking a disabled item has no effect (the card hides the controls); restore it first.
  - `set_progress` on a disabled item returns `item_disabled`.
- **Item set:** an item with only a disabled Magister label stays in the planner, shown as completed, so it can always be restored.
- **WebSocket** (`magister/homework/set_override`):
  - set or clear an override per the contract;
  - control permission;
  - errors `appointment_not_found`, `no_magister_label` (the appointment has no Magister InfoType 1–5), `label_not_found`, `invalid_format`, `unauthorized`.
- **Service:** `magister.set_homework_override` (appointment, mode: replace|disable|clear, label by id or name).
- **Calendar titles:** `[Proefwerk→Huiswerk]` for a replacement, nothing for disabled, the original when there is no override.
  The calendar updates on override changes.
- **Card:**
  - clicking or tapping the **Magister chip** (when enabled/online) opens a small menu: "Vervangen door…" with the child's
    label options except the original's own default label, "Uitschakelen", and, when overridden, "Herstellen";
  - an overridden chip is shown struck through (`<s>` with an aria description such as "vervangen" or "uitgeschakeld"), followed by the
    replacement chip in the manual-label style but without ×, since restoring goes through the menu;
  - disabled items are listed among the completed ones (visible with the "Afgerond" switch), struck through, with the
    progress controls hidden and the menu offering "Herstellen";
  - optimistic UI with rollback, NL/EN texts, keyboard and screen-reader accessible menu (menu button pattern).
- **Diagnostics:** counts of overrides per mode, with no names.

## Phases
One phase (backend + card) with Developer → Reviewer, followed by the verification round. Release **1.4.0**.

## Acceptance criteria
- [ ] Reviewed; CI green; versions 1.4.0; CHANGELOG; README NL/EN; screenshots from placeholder data showing a replaced chip.
- [ ] **PM test on HAOS:**
  - replace a Proefwerk with Huiswerk: the chip is struck through and Huiswerk follows; the weights, bars and calendar title show `[Proefwerk→Huiswerk]`;
  - disable a label: the item moves to completed, is struck through and has weight 0; it shows as completed in HA's to-do and is not in the count;
  - a disabled label plus a manual label keeps the item active;
  - restore both;
  - try to delete a label option that is used as a replacement (refused).
