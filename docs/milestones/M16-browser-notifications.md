# M16 — Browser notifications for the study timer (release 1.10.1)

| | |
|---|---|
| Status | **Draft — awaiting PM approval** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M15 · `frontend/src/timer-controller.ts`, `timer-views.ts`, `timer-card.ts` |

## Background
In 1.10.0 the website and the app's web view show only quiet signals: the card switches to "Tijd is om" and the HA
bell gets an entry. The PM wants a real notification when the website is open (2026-11-21).

## PM decisions (2026-11-21)
| # | Decision |
|---|---|
| 1 | When a Magister card is open, the browser shows a **notification** at the **pre-warning** and when the **time is up**. |
| 2 | A short **sound** is configurable: on or off. |

## Design (frontend only, no backend changes)
- **When it fires:**
  - The cards already detect both moments for `aria-live`; the same moments trigger the browser notification.
  - It fires only for a moment reached while the page is open. Like the announcements, a timer that is already past the moment when the card opens does not notify.
- **Texts:**
  - Pre-warning: "Nog {n} minuten: {title} ({subject})".
  - End: "Tijd is om: {title} ({subject})".
  - In NL or EN, following the HA language.
- **Notification options:**
  - `tag` per child, so a newer notification replaces the older one.
  - Clicking the notification focuses the HA window.
  - The notification has no action buttons, because buttons need a service worker; the student acts on the card.
- **One notification per moment, per browser.**
  - With several Magister cards on one page or in several tabs, only one notification is shown.
  - Coordination per child and moment through a `BroadcastChannel` (or `localStorage`), keyed by child, the timer's `started_at` and the moment.
- **Permission and settings per browser** (stored in `localStorage`; nothing in the backend, because the permission belongs to this browser):
  - In the ⚙ panel (homework card) and on the timer card (a small ⚙ or a link "Meldingen"):
    - **"Meldingen in deze browser"** (on/off). Switching it on asks the browser for permission (`Notification.requestPermission()`, which must be a user click).
    - **"Geluid"** (on/off, default on), shown when notifications are on.
  - If permission is denied or not supported, the panel says so: "Je browser staat meldingen niet toe", with a short hint.
  - Needs https. On http the option is hidden with an explanation.
- **Sound:**
  - A short built-in tone made with the Web Audio API, so no audio file is needed.
  - Played with the notification, and also while the tab is visible.
  - Browsers may block sound until the user has interacted with the page; then it is silently skipped.
- **The bell, the phone and the HA companion app stay as they are.**
  - In the companion app's web view, browser notifications are not available; the phone's own push notifications are used.
  - Suppress the browser notification when `navigator.userAgent` shows the HA app, if that is reliable; otherwise the option is simply not shown there.
- **Rights:** none needed. This only shows information the viewer can already see on the card. Anyone who opens the card may switch it on for their own browser. A parent who opens the card on their own computer can therefore also get browser notifications, by their own choice; the README says so.

## Tests
Vitest, with a mocked `Notification`, `BroadcastChannel` and `AudioContext`. Test that:
- the pre-warning and the end each notify once, also with two cards;
- no notification is shown for moments that passed before the card opened;
- permission handling works for denied, default and granted, and for an unsupported browser;
- the sound setting is respected;
- the texts are correct in NL and EN.

## Docs
README NL/EN, section "Studietimer":
- how to switch browser notifications on;
- that this works only while the page is open;
- the sound setting;
- that it applies per browser.

## Phases
One phase (card + docs), Developer → Reviewer (including headless Chromium with granted notification permission) → verification. Release **1.10.1**.

## Acceptance criteria
- [ ] Reviewed; CI green; version 1.10.1; CHANGELOG; README NL/EN.
- [ ] **PM test:**
  - open the dashboard in a browser and switch on notifications (allow), with the sound on;
  - start a 3-minute timer with a pre-warning of 2;
  - check the notification and sound at "Nog 2 minuten" and at "Tijd is om", also when another tab is in front;
  - switch the sound off and repeat.
