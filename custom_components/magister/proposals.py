"""Proposals for the daily maximum of a child (milestone M14).

The student decides about their own study time. The AI coach (of a student or of a
parent) never changes a maximum directly: it makes a proposal, which has no effect until
the student accepts it (on the card, or in the conversation after an explicit "yes").

Proposals live in the homework store of the config entry (key ``proposals``), per
child. There are two kinds: ``period`` (a maximum for the days of a period; accepted,
it becomes a circumstance) and ``weekdays`` (seven new weekday maximums; accepted,
they replace the child's). A proposal is ``proposed``, then ``accepted``, ``rejected``
or ``expired``: a period proposal expires when its first day starts unanswered, a
weekdays proposal 7 days after it was made. A child has at most 5 open proposals;
closed ones are kept for 14 days.

This module has no Home Assistant dependency; who may answer is decided in ``roles``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

from homeassistant.util import dt as dt_util

from .api.homework import WEEKDAYS, valid_weekday_max
from .api.mapping import LOCAL_TZ
from .context import ERR_INVALID_DAILY_MAX, ERR_INVALID_FORMAT, ContextError
from .roles import ANSWERED_BY_STUDENT, ANSWERED_ON_BEHALF

if TYPE_CHECKING:
    from .homework import HomeworkManager

STORE_KEY: Final = "proposals"

KIND_PERIOD: Final = "period"
KIND_WEEKDAYS: Final = "weekdays"
KINDS: Final = (KIND_PERIOD, KIND_WEEKDAYS)

STATUS_PROPOSED: Final = "proposed"
STATUS_ACCEPTED: Final = "accepted"
STATUS_REJECTED: Final = "rejected"
STATUS_EXPIRED: Final = "expired"
STATUSES: Final = (STATUS_PROPOSED, STATUS_ACCEPTED, STATUS_REJECTED, STATUS_EXPIRED)

ANSWER_ACCEPT: Final = "accept"
ANSWER_REJECT: Final = "reject"
ANSWERS: Final = (ANSWER_ACCEPT, ANSWER_REJECT)

MAX_OPEN: Final = 5
REASON_MAX: Final = 100
WEEKDAYS_EXPIRY: Final = timedelta(days=7)
KEEP_CLOSED: Final = timedelta(days=14)

PROPOSAL_ID: Final = re.compile(r"[0-9a-f]{8}")

ERR_PROPOSAL_NOT_FOUND: Final = "proposal_not_found"
ERR_PROPOSAL_CLOSED: Final = "proposal_closed"
ERR_TOO_MANY_PROPOSALS: Final = "too_many_proposals"
ERR_NOT_ALLOWED_TO_ANSWER: Final = "not_allowed_for_role"
ERR_INVALID_PERIOD: Final = "invalid_period"

WEEKDAY_NAMES: Final = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

NOT_ALLOWED_MESSAGE: Final = (
    "Only the student decides about the daily maximum. A parent (or an administrator) "
    "may answer only when the child has no active student user."
)


@dataclass(frozen=True, slots=True)
class Proposal:
    """One proposal for the daily maximum of a child."""

    id: str
    kind: str
    status: str
    reason: str
    created: datetime
    created_by: str
    start: date | None = None
    end: date | None = None
    minutes: int | None = None
    weekdays: tuple[int, ...] | None = None
    # Set when the proposal is closed (answered, or the moment it expired).
    closed: datetime | None = None
    answered_by: str | None = None

    def expires_at(self) -> datetime:
        """The moment an unanswered proposal expires."""
        if self.kind == KIND_PERIOD and self.start is not None:
            return datetime.combine(self.start, datetime.min.time(), LOCAL_TZ)
        return self.created + WEEKDAYS_EXPIRY

    def status_at(self, now: datetime) -> str:
        """The status now: an unanswered proposal past its expiry reads as expired."""
        if self.status == STATUS_PROPOSED and now >= self.expires_at():
            return STATUS_EXPIRED
        return self.status

    def is_open(self, now: datetime) -> bool:
        """Whether it still waits for an answer."""
        return self.status_at(now) == STATUS_PROPOSED

    def covers(self, day: date) -> bool:
        """Whether a period proposal covers the day."""
        return (
            self.kind == KIND_PERIOD
            and self.start is not None
            and self.end is not None
            and self.start <= day <= self.end
        )

    def stored(self) -> dict[str, Any]:
        """The form kept in the store."""
        data: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "reason": self.reason,
            "created": self.created.isoformat(),
            "created_by": self.created_by,
        }
        if self.start is not None:
            data["start"] = self.start.isoformat()
        if self.end is not None:
            data["end"] = self.end.isoformat()
        if self.minutes is not None:
            data["minutes"] = self.minutes
        if self.weekdays is not None:
            data["weekdays"] = list(self.weekdays)
        if self.closed is not None:
            data["closed"] = self.closed.isoformat()
        if self.answered_by is not None:
            data["answered_by"] = self.answered_by
        return data

    def view(self, now: datetime) -> dict[str, Any]:
        """The form the tools and the card payload show (no internal fields)."""
        data: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "status": self.status_at(now),
            "reason": self.reason,
            "created": self.created.astimezone(LOCAL_TZ).date().isoformat(),
            "created_by": self.created_by,
            "expires": self.expires_at().astimezone(LOCAL_TZ).date().isoformat(),
        }
        if self.kind == KIND_PERIOD:
            data["start"] = self.start.isoformat() if self.start else None
            data["end"] = self.end.isoformat() if self.end else None
            data["minutes"] = self.minutes
        else:
            data["weekdays"] = list(self.weekdays or ())
        if data["status"] != STATUS_PROPOSED:
            closed = self.closed or self.expires_at()
            data["closed"] = closed.astimezone(LOCAL_TZ).date().isoformat()
            data["answered_by"] = self.answered_by
        return data


def _parse_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    if parsed is None or parsed.tzinfo is None:
        return None
    return parsed


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def proposal_from_stored(raw: Any) -> Proposal | None:
    """A proposal from the store; ``None`` when it is not valid (it is dropped)."""
    if not isinstance(raw, dict):
        return None
    proposal_id, kind, status = raw.get("id"), raw.get("kind"), raw.get("status")
    created = _parse_datetime(raw.get("created"))
    reason = raw.get("reason")
    if (
        not isinstance(proposal_id, str)
        or not PROPOSAL_ID.fullmatch(proposal_id)
        or kind not in KINDS
        or status not in STATUSES
        or created is None
        or not isinstance(reason, str)
        or not reason.strip()
    ):
        return None
    start, end = _parse_date(raw.get("start")), _parse_date(raw.get("end"))
    minutes = valid_weekday_max(raw.get("minutes"))
    weekdays: tuple[int, ...] | None = None
    if kind == KIND_PERIOD:
        if start is None or end is None or end < start or minutes is None:
            return None
    else:
        values = raw.get("weekdays")
        if not isinstance(values, list) or len(values) != WEEKDAYS:
            return None
        checked = [valid_weekday_max(v) for v in values]
        if any(v is None for v in checked):
            return None
        weekdays = tuple(v for v in checked if v is not None)
    closed = _parse_datetime(raw.get("closed"))
    if status != STATUS_PROPOSED and closed is None:
        closed = created
    answered_by = raw.get("answered_by")
    return Proposal(
        id=proposal_id,
        kind=kind,
        status=status,
        reason=" ".join(reason.split())[:REASON_MAX],
        created=created,
        created_by="parent" if raw.get("created_by") == "parent" else "student",
        start=start if kind == KIND_PERIOD else None,
        end=end if kind == KIND_PERIOD else None,
        minutes=minutes if kind == KIND_PERIOD else None,
        weekdays=weekdays,
        closed=closed if status != STATUS_PROPOSED else None,
        answered_by=answered_by
        if status in (STATUS_ACCEPTED, STATUS_REJECTED)
        and answered_by in (ANSWERED_BY_STUDENT, ANSWERED_ON_BEHALF)
        else None,
    )


def clean_reason(value: Any) -> str:
    """The reason of a proposal: one line, 1 to 100 characters."""
    if not isinstance(value, str):
        raise ContextError(ERR_INVALID_FORMAT, "`reason` must be text")
    text = " ".join(value.split())
    if not text:
        raise ContextError(ERR_INVALID_FORMAT, "`reason` must not be empty")
    if len(text) > REASON_MAX:
        raise ContextError(
            ERR_INVALID_FORMAT, f"`reason` has at most {REASON_MAX} characters"
        )
    return text


def check_weekdays(value: Any) -> tuple[int, ...]:
    """Seven weekday maximums (Monday first), each 0 to 480 in steps of 15."""
    if not isinstance(value, list | tuple) or len(value) != WEEKDAYS:
        raise ContextError(
            ERR_INVALID_FORMAT,
            "`weekdays` is a list of 7 numbers, Monday first (monday to sunday)",
        )
    checked = [valid_weekday_max(v) for v in value]
    if any(v is None for v in checked):
        raise ContextError(
            ERR_INVALID_DAILY_MAX,
            "Each value in `weekdays` is 0 to 480 in steps of 15",
        )
    return tuple(v for v in checked if v is not None)


def answer_message(first_name: str, answered_by: str, *, accepted: bool) -> str:
    """The logbook text of an answer: only the first name of the user, never more."""
    verb = "geaccepteerd" if accepted else "afgewezen"
    suffix = " namens het kind" if answered_by == ANSWERED_ON_BEHALF else ""
    return f"voorstel dagmaximum {verb} door {first_name}{suffix}"


def first_name_of(name: str | None) -> str:
    """The first name of a Home Assistant user (``iemand`` when it has no name)."""
    parts = (name or "").split()
    return parts[0][:30] if parts else "iemand"


class ProposalBook:
    """The proposals of all children of one config entry."""

    def __init__(
        self,
        manager: HomeworkManager,
        on_change: Callable[[], None],
        on_expired: Callable[[int, Proposal], None],
    ) -> None:
        """Create the (empty) book; ``on_change`` saves and notifies."""
        self._manager = manager
        self._on_change = on_change
        self._on_expired = on_expired
        self._proposals: dict[int, list[Proposal]] = {}

    # -- storage ------------------------------------------------------------------

    def load(self, raw: Any) -> None:
        """Read the stored proposals (anything invalid is dropped)."""
        self._proposals = {}
        if not isinstance(raw, dict):
            return
        for key, stored in raw.items():
            if not isinstance(stored, list):
                continue
            try:
                child_id = int(key)
            except ValueError:
                continue
            seen: set[str] = set()
            clean: list[Proposal] = []
            for item in stored:
                proposal = proposal_from_stored(item)
                if proposal is not None and proposal.id not in seen:
                    seen.add(proposal.id)
                    clean.append(proposal)
            if clean:
                self._proposals[child_id] = clean

    def to_stored(self) -> dict[str, list[dict[str, Any]]]:
        """The proposals in the form of the store."""
        return {
            str(child_id): [p.stored() for p in proposals]
            for child_id, proposals in self._proposals.items()
            if proposals
        }

    def _store(self, child_id: int, proposals: list[Proposal]) -> None:
        if proposals:
            self._proposals[child_id] = proposals
        else:
            self._proposals.pop(child_id, None)
        self._on_change()

    # -- reading ------------------------------------------------------------------

    def all(self, child_id: int) -> list[Proposal]:
        """Every stored proposal of a child, oldest first."""
        return list(self._proposals.get(child_id, []))

    def listed(
        self, child_id: int, now: datetime, *, include_closed: bool = True
    ) -> list[Proposal]:
        """The open proposals first, then (optionally) the closed ones of 14 days."""
        found = [
            p
            for p in self._proposals.get(child_id, [])
            if p.is_open(now)
            or (include_closed and (p.closed or p.expires_at()) + KEEP_CLOSED >= now)
        ]
        return sorted(found, key=lambda p: (not p.is_open(now), p.created, p.id))

    def open_count(self, child_id: int, now: datetime) -> int:
        """The proposals that still wait for an answer."""
        return sum(1 for p in self._proposals.get(child_id, []) if p.is_open(now))

    def covering(self, child_id: int, day: date, now: datetime) -> Proposal | None:
        """The open period proposal with the lowest maximum that covers the day."""
        found = [
            p
            for p in self._proposals.get(child_id, [])
            if p.is_open(now) and p.covers(day)
        ]
        return min(found, key=lambda p: (p.minutes or 0, p.id), default=None)

    def payload(self, child_id: int, now: datetime) -> list[dict[str, Any]]:
        """The proposals of the card payload: the open ones and the closed ones kept."""
        return [p.view(now) for p in self.listed(child_id, now)]

    def statistics(self, now: datetime) -> dict[str, Any]:
        """Counts only: open proposals per kind and closed ones per status."""
        every = [p for ps in self._proposals.values() for p in ps]
        closed = [s for s in STATUSES if s != STATUS_PROPOSED]
        return {
            "open": {
                kind: sum(1 for p in every if p.kind == kind and p.is_open(now))
                for kind in KINDS
            },
            "closed": {
                status: sum(1 for p in every if p.status_at(now) == status)
                for status in closed
            },
        }

    def find(self, child_id: int, proposal_id: Any) -> Proposal:
        """A proposal of this child (``proposal_not_found`` otherwise)."""
        if isinstance(proposal_id, str):
            for proposal in self._proposals.get(child_id, []):
                if proposal.id == proposal_id:
                    return proposal
        raise ContextError(ERR_PROPOSAL_NOT_FOUND, "No such proposal")

    # -- writing --------------------------------------------------------------------

    def _new_id(self, child_id: int) -> str:
        taken = {p.id for p in self._proposals.get(child_id, [])}
        while (proposal_id := uuid.uuid4().hex[:8]) in taken:
            pass  # pragma: no cover
        return proposal_id

    def sync(self, now: datetime) -> bool:
        """Mark proposals that ran out as expired and prune the old closed ones.

        Returns whether anything changed (the caller saves). Each newly expired
        proposal is reported through ``on_expired`` (the logbook).
        """
        changed = False
        for child_id, proposals in list(self._proposals.items()):
            kept: list[Proposal] = []
            for proposal in proposals:
                if proposal.status == STATUS_PROPOSED and proposal.status_at(now) == (
                    STATUS_EXPIRED
                ):
                    proposal = replace(
                        proposal,
                        status=STATUS_EXPIRED,
                        closed=proposal.expires_at(),
                    )
                    self._on_expired(child_id, proposal)
                    changed = True
                if proposal.closed is not None and now - proposal.closed > KEEP_CLOSED:
                    changed = True
                    continue
                kept.append(proposal)
            if kept != proposals:
                changed = True
                if kept:
                    self._proposals[child_id] = kept
                else:
                    del self._proposals[child_id]
        return changed

    def propose(
        self,
        child_id: int,
        *,
        created_by: str,
        kind: Any,
        reason: Any,
        start: date | None = None,
        end: date | None = None,
        minutes: Any = None,
        weekdays: Any = None,
    ) -> Proposal:
        """Make a proposal; the fields of the kind and the limit are checked."""
        now = dt_util.utcnow()
        if self.sync(now):
            self._on_change()
        if kind not in KINDS:
            raise ContextError(ERR_INVALID_FORMAT, "`kind` is `period` or `weekdays`")
        text = clean_reason(reason)
        given = {
            "start": start is not None,
            "end": end is not None,
            "minutes": minutes is not None,
            "weekdays": weekdays is not None,
        }
        allowed = {"start", "end", "minutes"} if kind == KIND_PERIOD else {"weekdays"}
        extra = [
            name for name, present in given.items() if present and name not in allowed
        ]
        if extra:
            raise ContextError(
                ERR_INVALID_FORMAT,
                f"A {kind} proposal does not take: {', '.join(extra)}",
            )
        book = self._manager.context
        today = self._manager.today()
        values: tuple[int, ...] | None = None
        period: tuple[date, date] | None = None
        daily: int | None = None
        if kind == KIND_PERIOD:
            if minutes is None:
                raise ContextError(
                    ERR_INVALID_FORMAT, "A period proposal needs `minutes`"
                )
            if start is None or end is None:
                raise ContextError(
                    ERR_INVALID_FORMAT, "A period proposal needs start and end"
                )
            period = book.check_period(start, end)
            if period[0] <= today:
                raise ContextError(
                    ERR_INVALID_PERIOD,
                    "A period proposal starts tomorrow or later: it expires when "
                    "its first day starts without an answer.",
                )
            checked = valid_weekday_max(minutes)
            if checked is None:
                raise ContextError(
                    ERR_INVALID_DAILY_MAX,
                    "`minutes` is 0 to 480 in steps of 15",
                )
            daily = checked
        else:
            values = check_weekdays(weekdays)
            if values == self._manager.daily_max_weekdays(child_id):
                raise ContextError(
                    ERR_INVALID_FORMAT,
                    "These are already the current maximums of the weekdays.",
                )
        if self.open_count(child_id, now) >= MAX_OPEN:
            raise ContextError(
                ERR_TOO_MANY_PROPOSALS,
                f"At most {MAX_OPEN} open proposals per child; wait for an answer.",
            )
        if any(
            p.is_open(now)
            and p.kind == kind
            and p.start == (period[0] if period else None)
            and p.end == (period[1] if period else None)
            and p.minutes == daily
            and p.weekdays == values
            for p in self._proposals.get(child_id, [])
        ):
            raise ContextError(
                ERR_INVALID_FORMAT, "This proposal is already open; wait for an answer."
            )
        proposal = Proposal(
            id=self._new_id(child_id),
            kind=kind,
            status=STATUS_PROPOSED,
            reason=text,
            created=now,
            created_by=created_by,
            start=period[0] if period else None,
            end=period[1] if period else None,
            minutes=daily,
            weekdays=values,
        )
        self._store(child_id, [*self._proposals.get(child_id, []), proposal])
        return proposal

    def respond(
        self, child_id: int, proposal_id: Any, answer: Any, *, answered_by: str
    ) -> Proposal:
        """Accept or reject an open proposal (the rights are checked by the caller)."""
        if answer not in ANSWERS:
            raise ContextError(ERR_INVALID_FORMAT, "`answer` is `accept` or `reject`")
        now = dt_util.utcnow()
        if self.sync(now):
            self._on_change()
        proposal = self.find(child_id, proposal_id)
        if proposal.status != STATUS_PROPOSED:
            raise ContextError(
                ERR_PROPOSAL_CLOSED,
                f"This proposal is already {proposal.status}.",
            )
        accepted = answer == ANSWER_ACCEPT
        if accepted:
            self._apply(child_id, proposal, answered_by)
        answered = replace(
            proposal,
            status=STATUS_ACCEPTED if accepted else STATUS_REJECTED,
            closed=now,
            answered_by=answered_by,
        )
        self._store(
            child_id,
            [answered if p.id == proposal.id else p for p in self._proposals[child_id]],
        )
        return answered

    def _apply(self, child_id: int, proposal: Proposal, answered_by: str) -> None:
        """The effect of an accepted proposal."""
        if proposal.kind == KIND_PERIOD:
            assert proposal.start and proposal.end and proposal.minutes is not None
            self._manager.context.add_accepted_period(
                child_id,
                start=proposal.start,
                end=proposal.end,
                text=proposal.reason,
                minutes=proposal.minutes,
                created_by="student"
                if answered_by == ANSWERED_BY_STUDENT
                else "parent",
            )
        else:
            assert proposal.weekdays is not None
            self._manager.set_weekday_max(child_id, proposal.weekdays)

    def drop_children(self, keep: Iterable[int]) -> None:
        """Forget the proposals of children that are no longer part of the entry."""
        stay = set(keep)
        gone = [child_id for child_id in self._proposals if child_id not in stay]
        for child_id in gone:
            del self._proposals[child_id]
        if gone:
            self._on_change()
