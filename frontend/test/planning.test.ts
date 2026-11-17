import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyProposalOverlay,
  dayMaximum,
  formatMinutesShort,
  formatRange,
  proposedMaximum,
  weekdayIndex,
} from "../src/logic";
import { MagisterHomeworkCard } from "../src/magister-homework-card";
import type { HomeworkItem, HomeworkPayload, Proposal, Subtask } from "../src/types";
import { item } from "./fixtures";
import { flush, mount, root, wsError } from "./helpers";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date", "setTimeout", "clearTimeout"] });
  vi.setSystemTime(new Date("2026-11-13T09:30:00Z"));
  window.localStorage.clear();
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const PARENT = "school.example.net:1:50";
const MONDAY = "2026-11-16";
const SATURDAY = "2026-11-14";
const WEEKDAYS = [90, 90, 90, 90, 90, 150, 0];

function sub(id: string, overrides: Partial<Subtask> = {}): Subtask {
  return {
    uid: `${PARENT}:sub:${id}`,
    title: `Stap ${id}`,
    planned: MONDAY,
    date: MONDAY,
    overdue: false,
    progress: 0,
    completed: false,
    last_partial: 0,
    ...overrides,
  };
}

function withSubs(subtasks: Subtask[], overrides: Partial<HomeworkItem> = {}): HomeworkItem {
  return item({
    uid: PARENT,
    date: "2026-11-17",
    due: "2026-11-17T10:00:00+01:00",
    subject: "Engels",
    derived: subtasks.length > 0,
    subtasks,
    ...overrides,
  });
}

function proposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    id: "a1b2c3d4",
    kind: "period",
    status: "proposed",
    reason: "Toetsweek",
    created: "2026-11-13",
    created_by: "student",
    expires: "2026-11-16",
    start: MONDAY,
    end: "2026-11-20",
    minutes: 120,
    ...overrides,
  };
}

function plan(items: HomeworkItem[], extra: Partial<HomeworkPayload> = {}): HomeworkPayload {
  return { available: true, items, daily_max_minutes: 90, daily_max_weekdays: WEEKDAYS, ...extra };
}

const q = (card: MagisterHomeworkCard, selector: string): HTMLElement => {
  const found = root(card).querySelector<HTMLElement>(selector);
  if (!found) throw new Error(`no ${selector}`);
  return found;
};
const qb = q as (card: MagisterHomeworkCard, selector: string) => HTMLButtonElement;
const qa = (card: MagisterHomeworkCard, selector: string): HTMLElement[] => [
  ...root(card).querySelectorAll<HTMLElement>(selector),
];
const head = (card: MagisterHomeworkCard, date: string): HTMLElement | null =>
  root(card).querySelector(`#day-${date}`)?.closest("section") ?? null;
const total = (card: MagisterHomeworkCard, date: string): HTMLElement | null =>
  head(card, date)?.querySelector<HTMLElement>(".planned") ?? null;

async function setup(
  data: HomeworkPayload,
  options: { callWS?: unknown; language?: string; config?: Record<string, unknown> } = {},
) {
  const callWS = options.callWS ?? vi.fn().mockResolvedValue({ proposal: proposal() });
  const { card, connection } = await mount(options.config ?? {}, callWS, options.language);
  connection.push(data);
  await flush(card);
  return { card, connection, callWS: callWS as ReturnType<typeof vi.fn> };
}

describe("the effective maximum of a date", () => {
  it("numbers the weekdays from Monday, in the local date", () => {
    expect(weekdayIndex("2026-11-16")).toBe(0);
    expect(weekdayIndex("2026-11-20")).toBe(4);
    expect(weekdayIndex("2026-11-21")).toBe(5);
    expect(weekdayIndex("2026-11-22")).toBe(6);
    expect(weekdayIndex("nonsense")).toBe(-1);
  });

  it("uses the weekday value, an override of that date, or the old single maximum", () => {
    const data = plan([], { daily_max_overrides: { "2026-11-17": 30, "2026-11-21": 150 } });
    expect(dayMaximum(data, MONDAY)).toEqual({ max: 90, normal: 90, adjusted: false });
    expect(dayMaximum(data, "2026-11-22")).toEqual({ max: 0, normal: 0, adjusted: false });
    expect(dayMaximum(data, "2026-11-17")).toEqual({ max: 30, normal: 90, adjusted: true });
    // an override equal to that weekday's value is not "adjusted", even if the Monday value differs
    expect(dayMaximum(data, "2026-11-21")).toEqual({ max: 150, normal: 150, adjusted: false });
    const old = { daily_max_minutes: 60, daily_max_overrides: { [MONDAY]: 60, "2026-11-17": 45 } };
    expect(dayMaximum(old, MONDAY)).toEqual({ max: 60, normal: 60, adjusted: false });
    expect(dayMaximum(old, "2026-11-17")).toEqual({ max: 45, normal: 60, adjusted: true });
    expect(dayMaximum({}, MONDAY)).toEqual({ max: undefined, normal: undefined, adjusted: false });
    expect(dayMaximum(undefined, MONDAY).max).toBeUndefined();
    // a malformed list of weekdays is ignored
    expect(dayMaximum({ daily_max_weekdays: [1, 2], daily_max_minutes: 45 }, MONDAY).max).toBe(45);
  });

  it("formats the texts of the proposals", () => {
    expect(formatMinutesShort(90, "nl")).toBe("1 u 30");
    expect(formatMinutesShort(90, "en")).toBe("1 h 30");
    expect(formatMinutesShort(120, "nl")).toBe("2 u");
    expect(formatMinutesShort(45, "nl")).toBe("45 min");
    expect(formatRange("2026-11-23", "2026-11-27", "nl")).toBe("23–27 nov");
    expect(formatRange("2026-11-23", "2026-11-27", "en-GB")).toBe("23–27 Nov");
    expect(formatRange("2026-11-30", "2026-12-04", "nl")).toBe("30 nov – 4 dec");
    expect(formatRange("2026-11-23", "2026-11-23", "nl")).toBe("23 nov");
    expect(formatRange("x", "y", "nl")).toBe("x – y");
  });

  it("finds the lowest open period proposal that covers a date", () => {
    const list = [
      proposal(),
      proposal({ id: "b", minutes: 60, start: "2026-11-18", end: "2026-11-18" }),
      proposal({ id: "c", minutes: 15, status: "rejected" }),
      proposal({ id: "d", kind: "weekdays", weekdays: WEEKDAYS }),
    ];
    expect(proposedMaximum(list, MONDAY)).toBe(120);
    expect(proposedMaximum(list, "2026-11-18")).toBe(60);
    expect(proposedMaximum(list, "2026-11-21")).toBeUndefined();
    const overlay = new Map([["a1b2c3d4", { status: "accepted" as const }]]);
    expect(applyProposalOverlay(list, overlay)[0]?.status).toBe("accepted");
    expect(proposedMaximum(applyProposalOverlay(list, overlay), MONDAY)).toBeUndefined();
  });
});

describe("subtask rows and the marker", () => {
  it("styles subtask rows with a theme colour, a left border and a tint, with a fallback", () => {
    const css = MagisterHomeworkCard.styles.toString();
    expect(css).toContain("--sub-color: var(--info-color, #039be5)");
    expect(css).toMatch(/\.item\.subtask\s*{[^}]*border-left-color: var\(--sub-color\)/);
    expect(css).toMatch(/\.item\.subtask\s*{[^}]*background: color-mix\(in srgb, var\(--sub-color\) 10%/);
    // the text colour mixes in the theme's text colour: contrast in light and dark
    expect(css).toMatch(/--sub-text: color-mix\([^;]*var\(--primary-text-color/);
  });

  it("keeps the AI and parent chips on subtask rows", async () => {
    const { card } = await setup(
      plan([withSubs([sub("a", { created_by: "ai" }), sub("b", { created_by: "parent" })])]),
    );
    const rows = qa(card, "li.item.subtask");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.querySelector(".ai-badge")?.getAttribute("aria-label")).toBe("Created by AI coach");
    expect(rows[1]?.querySelector(".parent-badge")?.textContent.trim()).toBe("Parent");
  });

  it("shows a marker with the count on an item that has subtasks, next to the title", async () => {
    const subs = [sub("a"), sub("b"), sub("c", { date: "2026-11-17", planned: "2026-11-17" })];
    const { card } = await setup(plan([withSubs(subs)]));
    const marker = q(card, `li[data-uid="${PARENT}"] .sub-marker`);
    expect(marker.textContent.trim()).toBe("3 subtasks");
    expect(marker.getAttribute("role")).toBe("img");
    expect(marker.getAttribute("aria-label")).toBe("has 3 subtasks");
    expect(marker.getAttribute("title")).toBe("has 3 subtasks");
    expect(marker.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    // next to the subject, inside the item's head
    expect(marker.previousElementSibling?.classList.contains("subject")).toBe(true);
    // the progress line stays
    expect(q(card, ".sub-count").textContent.trim()).toBe("0 of 3 subtasks");
  });

  it("says one subtask in the singular, in Dutch too, and shows no marker without subtasks", async () => {
    const one = await setup(plan([withSubs([sub("a")])]), { language: "nl" });
    const marker = q(one.card, ".sub-marker");
    expect(marker.textContent.trim()).toBe("1 deelstap");
    expect(marker.getAttribute("aria-label")).toBe("heeft 1 deelstap");
    document.body.innerHTML = "";
    const many = await setup(plan([withSubs([sub("a"), sub("b")])]), { language: "nl" });
    expect(q(many.card, ".sub-marker").getAttribute("aria-label")).toBe("heeft 2 deelstappen");
    document.body.innerHTML = "";
    const none = await setup(plan([withSubs([])]));
    expect(root(none.card).querySelector(".sub-marker")).toBeNull();
  });

  it("shows no marker on a disabled item", async () => {
    const { card } = await setup(
      plan([withSubs([sub("a")], { disabled: true, completed: true, override: { mode: "disable" } })]),
      { config: { show_completed: true } },
    );
    expect(root(card).querySelector(".sub-marker")).toBeNull();
  });
});

describe("the day total per weekday", () => {
  const SAT = sub("s", { minutes: 120, date: SATURDAY, planned: SATURDAY });
  const MON = sub("m", { minutes: 120 });

  it("uses the maximum of that weekday: a weekend day can differ without being adjusted", async () => {
    const { card } = await setup(plan([withSubs([SAT, MON])]));
    // Saturday allows 150 minutes: no warning, and not adjusted
    expect(total(card, SATURDAY)?.getAttribute("class")).toBe("planned");
    expect(total(card, SATURDAY)?.textContent).toContain("± 2 h planned");
    expect(total(card, SATURDAY)?.textContent).not.toContain("max");
    // Monday allows 90: over
    expect(total(card, MONDAY)?.getAttribute("class")).toBe("planned over");
    expect(total(card, MONDAY)?.textContent).toContain("/ max 1 h 30 min");
  });

  it("shows a circumstance as adjusted when it differs from that weekday's value", async () => {
    const { card } = await setup(
      plan([withSubs([SAT, MON])], { daily_max_overrides: { [SATURDAY]: 90, [MONDAY]: 90 } }),
    );
    // Saturday: 90 differs from 150 -> adjusted and over
    const saturday = total(card, SATURDAY);
    expect(saturday?.getAttribute("class")).toBe("planned over adjusted");
    expect(saturday?.textContent).toContain("/ max 1 h 30 min (adjusted)");
    // Monday: 90 equals Monday's value: plain over, not adjusted
    expect(total(card, MONDAY)?.getAttribute("class")).toBe("planned over");
  });

  it("warns on a day whose maximum is 0 and says that no study time is set", async () => {
    const sunday = sub("z", { minutes: 30, date: "2026-11-15", planned: "2026-11-15" });
    const { card } = await setup(plan([withSubs([sunday])]));
    const node = total(card, "2026-11-15");
    expect(node?.getAttribute("class")).toBe("planned over");
    expect(node?.textContent).toContain("⚠");
    expect(node?.textContent).toContain("/ max 0 min");
    expect(node?.querySelector(".sr-only")?.textContent).toBe(", no study time set for this day (0 min)");
  });

  it("falls back to daily_max_minutes for an old payload", async () => {
    const old: HomeworkPayload = { available: true, items: [withSubs([MON, SAT])], daily_max_minutes: 60 };
    const { card } = await setup(old);
    expect(total(card, MONDAY)?.getAttribute("class")).toBe("planned over");
    expect(total(card, SATURDAY)?.getAttribute("class")).toBe("planned over");
    expect(total(card, MONDAY)?.textContent).toContain("/ max 1 h");
  });
});

describe("proposals", () => {
  const WEEKDAY_PROPOSAL = proposal({
    id: "f00dbabe",
    kind: "weekdays",
    reason: "Rustiger weekend",
    weekdays: [90, 90, 90, 90, 90, 0, 30],
    expires: "2026-11-20",
  });
  delete WEEKDAY_PROPOSAL.start;
  delete WEEKDAY_PROPOSAL.end;
  delete WEEKDAY_PROPOSAL.minutes;

  it("shows an open period proposal at the top with Accept and Reject", async () => {
    const { card } = await setup(plan([withSubs([sub("a")])], { proposals: [proposal()] }));
    const block = q(card, ".proposal");
    expect(block.getAttribute("role")).toBe("group");
    expect(block.querySelector(".proposal-text")?.textContent.replace(/\s+/g, " ").trim()).toBe(
      "Proposal from the coach: Toetsweek 16–20 Nov, max 2 h per day Expires on Mon 16 Nov",
    );
    expect(qa(card, ".proposal button").map((b) => b.textContent.trim())).toEqual(["Accept", "Reject"]);
    // it is the first thing in the card
    expect(root(card).querySelector(".content")?.firstElementChild).toBe(q(card, ".proposals"));
    expect(block.getAttribute("aria-label")).toBe(
      "Proposal from the coach: Toetsweek 16–20 Nov, max 2 h per day",
    );
    expect(qb(card, "[data-accept]").getAttribute("aria-label")).toBe(
      "Accept proposal: Toetsweek 16–20 Nov, max 2 h per day",
    );
  });

  it("shows the seven values of a weekday proposal, in Dutch", async () => {
    const { card } = await setup(plan([], { proposals: [WEEKDAY_PROPOSAL] }), { language: "nl" });
    expect(q(card, ".proposal-text").textContent.replace(/\s+/g, " ")).toContain(
      "Voorstel van de coach: Rustiger weekend, max per dag: ma 1 u 30, di 1 u 30, wo 1 u 30, do 1 u 30, vr 1 u 30, za geen, zo 30 min",
    );
    expect(qa(card, ".proposal button").map((b) => b.textContent.trim())).toEqual([
      "Accepteren",
      "Afwijzen",
    ]);
  });

  it("shows no block without open proposals", async () => {
    const closed = proposal({ status: "accepted", closed: "2026-11-13", answered_by: "student" });
    const { card } = await setup(plan([withSubs([sub("a")])], { proposals: [closed] }));
    expect(root(card).querySelector(".proposals")).toBeNull();
    const old = await setup({ available: true, items: [withSubs([sub("a")])] });
    expect(root(old.card).querySelector(".proposals")).toBeNull();
  });

  it("asks to confirm an accept, and sends nothing before that", async () => {
    const answered = proposal({ status: "accepted", closed: "2026-11-13", answered_by: "student" });
    const callWS = vi.fn().mockResolvedValue({ proposal: answered });
    const { card, callWS: ws } = await setup(plan([], { proposals: [proposal()] }), { callWS });
    qb(card, "[data-accept]").click();
    await flush(card);
    expect(ws).not.toHaveBeenCalled();
    const confirm = q(card, ".proposal .confirm");
    expect(confirm.textContent).toContain("Accept this proposal? It applies at once.");
    // the focus goes to Cancel (the safe choice); Escape cancels and returns to Accept
    expect(root(card).activeElement).toBe(q(card, ".proposal .confirm .cancel"));
    confirm.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, composed: true }));
    await flush(card);
    expect(root(card).querySelector(".proposal .confirm")).toBeNull();
    expect(root(card).activeElement).toBe(qb(card, "[data-accept]"));
    expect(ws).not.toHaveBeenCalled();
    // confirm
    qb(card, "[data-accept]").click();
    await flush(card);
    qb(card, ".proposal .confirm .primary").click();
    await flush(card);
    expect(ws).toHaveBeenCalledTimes(1);
    expect(ws).toHaveBeenCalledWith({
      type: "magister/homework/respond_proposal",
      entity_id: "todo.kind_myschool_homework",
      proposal: "a1b2c3d4",
      answer: "accept",
    });
    expect(root(card).querySelector(".proposals")).toBeNull();
    expect(q(card, ".toast").textContent).toContain("Proposal accepted.");
  });

  it("rejects at once, optimistically, and keeps the answer until the push", async () => {
    const rejected = proposal({ status: "rejected", closed: "2026-11-13", answered_by: "student" });
    let resolve: (value: unknown) => void = () => undefined;
    const callWS = vi.fn().mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    const { card, connection } = await setup(plan([], { proposals: [proposal()] }), { callWS });
    qb(card, "[data-reject]").click();
    await flush(card);
    expect(callWS).toHaveBeenCalledWith(expect.objectContaining({ answer: "reject", proposal: "a1b2c3d4" }));
    // optimistic: gone while the request is in flight
    expect(root(card).querySelector(".proposal")).toBeNull();
    resolve({ proposal: rejected });
    await flush(card);
    expect(root(card).querySelector(".proposal")).toBeNull();
    expect(q(card, ".toast").textContent).toContain("Proposal rejected.");
    // the push confirms it
    connection.push(plan([], { proposals: [rejected] }));
    await flush(card);
    expect(root(card).querySelector(".proposal")).toBeNull();
  });

  it.each([
    ["not_allowed_for_role", "Only the student can answer this proposal."],
    ["proposal_closed", "This proposal has already been answered or has expired."],
    [
      "too_many_notes",
      "The proposal cannot be accepted: there are already 50 notes for this child. Delete a note first.",
    ],
    ["proposal_not_found", "This proposal no longer exists."],
    ["unauthorized", "You have no permission to answer proposals."],
    ["something_else", "Answering failed. The change was rolled back."],
  ])("rolls back and shows a translated message for %s", async (code, message) => {
    const callWS = vi.fn().mockRejectedValue(wsError(code));
    const { card } = await setup(plan([], { proposals: [proposal()] }), { callWS });
    qb(card, "[data-reject]").click();
    await flush(card);
    // rolled back: the proposal is open again
    expect(qa(card, ".proposal")).toHaveLength(1);
    const toast = q(card, ".toast");
    expect(toast.getAttribute("role")).toBe("alert");
    expect(toast.querySelector("span")?.textContent).toBe(message);
    expect(qb(card, "[data-reject]").disabled).toBe(false);
  });

  it("translates the not-allowed message into Dutch", async () => {
    const callWS = vi.fn().mockRejectedValue(wsError("not_allowed_for_role"));
    const { card } = await setup(plan([], { proposals: [proposal()] }), { callWS, language: "nl" });
    qb(card, "[data-accept]").click();
    await flush(card);
    qb(card, ".proposal .confirm .primary").click();
    await flush(card);
    expect(q(card, ".toast span").textContent).toBe("Alleen de leerling kan dit voorstel beantwoorden.");
    expect(qa(card, ".proposal")).toHaveLength(1);
  });

  it("moves the focus to the next proposal when one is answered", async () => {
    const second = proposal({ id: "0badc0de", reason: "Tweede" });
    const callWS = vi.fn().mockResolvedValue({
      proposal: proposal({ status: "rejected", closed: "2026-11-13" }),
    });
    const { card } = await setup(plan([], { proposals: [proposal(), second] }), { callWS });
    expect(qa(card, ".proposal")).toHaveLength(2);
    qb(card, '[data-reject="a1b2c3d4"]').click();
    await flush(card);
    expect(qa(card, ".proposal")).toHaveLength(1);
    expect(root(card).activeElement?.closest(".proposal")?.getAttribute("data-proposal")).toBe("0badc0de");
  });

  it("disables the buttons while the card is read-only", async () => {
    const { card } = await setup(plan([], { proposals: [proposal()], available: false }));
    expect(qa(card, ".proposal button").every((b) => (b as HTMLButtonElement).disabled)).toBe(true);
  });

  it("notes the proposed maximum on the days it covers, without changing the day total", async () => {
    const { card } = await setup(
      plan([withSubs([sub("a", { minutes: 60 })])], { proposals: [proposal()] }),
    );
    const day = head(card, MONDAY);
    const note = day?.querySelector<HTMLElement>(".proposed-max");
    expect(note?.querySelector('[aria-hidden="true"]')?.textContent).toBe("proposal: max 2 h");
    expect(note?.querySelector(".sr-only")?.textContent).toBe("proposal, not accepted yet: max 2 h");
    // the day total is unchanged by the proposal
    expect(day?.querySelector(".planned")?.textContent.trim()).toBe("± 1 h planned");
  });

  it("drops the day note once the proposal is answered", async () => {
    const callWS = vi.fn().mockResolvedValue({ proposal: proposal({ status: "rejected" }) });
    const { card } = await setup(
      plan([withSubs([sub("a", { minutes: 60 })])], { proposals: [proposal()] }),
      { callWS },
    );
    // Monday (a subtask) and Tuesday (the item) are both covered
    expect(qa(card, ".proposed-max")).toHaveLength(2);
    qb(card, "[data-reject]").click();
    await flush(card);
    expect(qa(card, ".proposed-max")).toHaveLength(0);
  });

  it("lists answered and expired proposals with their status under the Earlier switch", async () => {
    const closed = [
      proposal({ id: "1", status: "accepted", closed: "2026-11-12", answered_by: "student" }),
      proposal({ id: "2", status: "accepted", closed: "2026-11-12", answered_by: "on_behalf" }),
      proposal({ id: "3", status: "rejected", closed: "2026-11-11", answered_by: "student", reason: "Anders" }),
      proposal({ id: "4", status: "expired", closed: "2026-11-10", answered_by: null }),
    ];
    const { card } = await setup(plan([withSubs([sub("a")])], { proposals: [...closed, WEEKDAY_PROPOSAL] }));
    expect(root(card).querySelector(".closed-proposals")).toBeNull();
    qb(card, ".switch[aria-label='Show earlier days']").click();
    await flush(card);
    expect(q(card, ".closed-proposals h3").textContent).toBe("Earlier proposals");
    const rows = qa(card, ".closed-proposal").map((row) => row.textContent.replace(/\s+/g, " ").trim());
    expect(rows).toEqual([
      "accepted on Thu 12 Nov Toetsweek 16–20 Nov, max 2 h per day",
      "accepted on behalf of the child on Thu 12 Nov Toetsweek 16–20 Nov, max 2 h per day",
      "rejected on Wed 11 Nov Anders 16–20 Nov, max 2 h per day",
      "expired on Tue 10 Nov Toetsweek 16–20 Nov, max 2 h per day",
    ]);
    // the open proposal stays at the top, not in the list
    expect(qa(card, ".proposal")).toHaveLength(1);
  });

  it("shows an answered proposal in the list at once when Earlier is on", async () => {
    const callWS = vi.fn().mockResolvedValue({
      proposal: proposal({ status: "accepted", closed: "2026-11-13", answered_by: "student" }),
    });
    const { card } = await setup(plan([], { proposals: [proposal()] }), {
      callWS,
      config: { show_past: true },
    });
    qb(card, "[data-accept]").click();
    await flush(card);
    qb(card, ".proposal .confirm .primary").click();
    await flush(card);
    expect(q(card, ".closed-proposal").textContent.replace(/\s+/g, " ")).toContain("accepted on Fri 13 Nov");
  });

  it("is usable with the keyboard: native buttons in a labelled group", async () => {
    const { card } = await setup(plan([], { proposals: [proposal()] }));
    const buttons = qa(card, ".proposal button");
    expect(buttons.every((b) => b.tagName === "BUTTON" && b.getAttribute("type") === "button")).toBe(true);
    expect(buttons.every((b) => (b.getAttribute("aria-label") ?? "").length > 0)).toBe(true);
  });
});
