"""AI homework coach: an LLM API (``magister_coach``) with tools for the planner.

Home Assistant's own ``mcp_server`` integration serves the API to MCP clients (and the
conversation agents can use it too). Every tool call carries ``context.user_id``; a tool
only touches children whose coach is enabled **and** linked to that user. Nothing here
writes to Magister, and no teacher names or codes ever leave this module: the tools hand
out the planner payloads of the homework to-do entities (which have none) plus the
schedule without teachers. Item ids are the appointment ids, without the school host.

Business rules and validation are those of the WebSocket API and the services: the write
tools call the same methods of the homework to-do entity.

Access control: the coach intentionally skips Home Assistant's entity ``POLICY_CONTROL``
check. Linking a user to a child (an administrator does that in the options) is the
explicit grant; the tools are the only door and they only reach the linked children.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Final

import probatio
from homeassistant.components.logbook import async_log_entry
from homeassistant.components.todo.const import DATA_COMPONENT
from homeassistant.components.todo.const import DOMAIN as TODO_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import llm
from homeassistant.util import dt as dt_util

from .api.homework import (
    CREATED_BY_AI,
    MAX_SUBTASKS,
    MODE_CLEAR,
    MODE_DISABLE,
    MODE_REPLACE,
    NOTE_MAX,
    SUBTASK_TITLE_MAX,
    magister_label_option,
)
from .api.mapping import CANCELLED_STATUSES, LOCAL_TZ
from .coach_text import DEFAULT_GUIDELINES, PLANNER_RULES
from .const import (
    CHILD_ID,
    CHILD_NAME,
    CHILD_SHORT_NAME,
    COACH_ENABLED,
    COACH_GUIDELINES,
    COACH_USERS,
    CONF_CHILDREN,
    CONF_COACH,
    CONF_HOST,
    DOMAIN,
)
from .coordinator import MagisterConfigEntry
from .homework import (
    ERR_ITEM_DISABLED,
    ERR_ITEM_NOT_FOUND,
    HomeworkManager,
    LabelError,
    Payload,
    appointment_to_dict,
    item_to_dict,
    progress_payload,
    strict_progress,
    subtask_title,
)
from .homework import note_text as validate_note
from .todo import HomeworkItemDisabled, HomeworkItemHasSubtasks, MagisterHomeworkTodo
from .ws_api import (
    ERR_INVALID_FORMAT,
    ERR_ITEM_HAS_SUBTASKS,
    ERR_NOT_FOUND,
    INVALID_INPUT,
)

_LOGGER = logging.getLogger(__name__)

COACH_API_ID: Final = "magister_coach"
COACH_API_NAME: Final = "Magister huiswerkcoach"
_UNREGISTER: Final = f"{DOMAIN}_coach_api"

ERR_NOT_LINKED: Final = "not_linked"
ERR_CHILD_REQUIRED: Final = "child_required"
ERR_CHILD_NOT_FOUND: Final = "child_not_found"
ERR_INTERNAL: Final = "internal_error"

MAX_SCHEDULE_DAYS: Final = 31
LOG_NAME: Final = "Magister"
_ID = re.compile(r"\d+(:sub:[A-Za-z0-9_-]+)?")
_APPOINTMENT_ID = re.compile(r"\d+")

NOT_LINKED_HELP: Final = (
    "This Home Assistant user is not linked to a child. An administrator can link the "
    "user in Settings > Devices & services > Magister > Configure > AI-coach."
)


@dataclass(frozen=True, slots=True)
class CoachChild:
    """A child this user may coach."""

    entry: MagisterConfigEntry
    child_id: int
    name: str
    guidelines: str
    suffix: str = ""

    @property
    def id(self) -> str:
        """The id the tools use (with a short entry suffix when ids collide)."""
        return f"{self.child_id}-{self.suffix}" if self.suffix else str(self.child_id)

    @property
    def manager(self) -> HomeworkManager:
        """The homework manager of the entry."""
        manager: HomeworkManager = self.entry.runtime_data.homework
        return manager

    @property
    def host(self) -> str:
        """The school host (never sent to the AI)."""
        return str(self.entry.data[CONF_HOST])


class CoachError(Exception):
    """A tool call that fails with a code of the contract (or a coach code)."""

    def __init__(self, code: str, message: str | None = None) -> None:
        """Remember the code and the explanation."""
        super().__init__(code)
        self.code = code
        self.message = message or code


def error_result(code: str, message: str | None = None) -> llm.ToolResult:
    """The structured error of a tool."""
    return llm.ToolResult(data={"error": code, "message": message or code}, error=True)


# -- access -------------------------------------------------------------------------


def coach_settings(entry: MagisterConfigEntry, child_id: int) -> dict[str, Any]:
    """The stored coach settings of a child (empty when none)."""
    stored = entry.options.get(CONF_COACH)
    settings = stored.get(str(child_id)) if isinstance(stored, dict) else None
    return settings if isinstance(settings, dict) else {}


def guidelines_of(settings: dict[str, Any]) -> str:
    """The coaching guidelines: the stored text, or the default when empty."""
    text = settings.get(COACH_GUIDELINES)
    return (
        text.strip() if isinstance(text, str) and text.strip() else DEFAULT_GUIDELINES
    )


def coach_name(child: dict[str, Any], position: int) -> str:
    """The name the coach uses: never a full name (``Kind 1`` when only that is known).

    The stored short name is the first name or the initials, but falls back to the full
    name when Magister gave neither; a full name has spaces and equals the stored name.
    """
    short = str(child[CHILD_SHORT_NAME]).strip()
    if short and short != str(child.get(CHILD_NAME, "")).strip():
        return short
    return f"Kind {position + 1}"


def _entry_suffix(entry: MagisterConfigEntry) -> str:
    """A short stable tag of an entry (not the school host)."""
    return hashlib.sha256(entry.entry_id.encode()).hexdigest()[:8]


@callback
def async_accessible_children(
    hass: HomeAssistant, user_id: str | None
) -> list[CoachChild]:
    """The children whose coach is enabled and linked to the (active) user."""
    found: list[tuple[MagisterConfigEntry, dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, int]] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        for child in entry.data[CONF_CHILDREN]:
            child_id = int(child[CHILD_ID])
            if (str(entry.data[CONF_HOST]), child_id) in seen:
                continue  # the same child under two entries (legacy): the first wins
            settings = coach_settings(entry, child_id)
            users = settings.get(COACH_USERS)
            if (
                settings.get(COACH_ENABLED) is True
                and isinstance(users, list)
                and user_id in users
            ):
                seen.add((str(entry.data[CONF_HOST]), child_id))
                found.append((entry, child, settings))
    # ``Kind N`` counts within what this user may access, not within the entry.
    children = [
        CoachChild(
            entry,
            int(child[CHILD_ID]),
            coach_name(child, position),
            guidelines_of(settings),
        )
        for position, (entry, child, settings) in enumerate(found)
    ]
    # Children of different schools can share an id: tell those apart by a short tag of
    # their entry, so that a reference never means two children.
    counts = Counter(c.child_id for c in children)
    return [
        replace(c, suffix=_entry_suffix(c.entry)) if counts[c.child_id] > 1 else c
        for c in children
    ]


async def async_user_children(
    hass: HomeAssistant, context: Context | None
) -> list[CoachChild]:
    """The children of the user behind a request (none if unknown or inactive)."""
    user_id = context.user_id if context else None
    if not user_id:
        return []
    user = await hass.auth.async_get_user(user_id)
    if user is None or not user.is_active or user.system_generated:
        return []
    return async_accessible_children(hass, user_id)


def pick_child(children: list[CoachChild], reference: Any) -> CoachChild:
    """The child a tool call is about (``CoachError`` when it is not allowed)."""
    if not children:
        raise CoachError(ERR_NOT_LINKED, NOT_LINKED_HELP)
    if reference is None or str(reference).strip() == "":
        if len(children) == 1:
            return children[0]
        raise CoachError(
            ERR_CHILD_REQUIRED,
            "Pass `child`: one of " + ", ".join(f"{c.id} ({c.name})" for c in children),
        )
    wanted = str(reference).strip()
    for child in children:
        if child.id == wanted:
            return child
    by_name = [c for c in children if c.name.casefold() == wanted.casefold()]
    if len(by_name) == 1:
        return by_name[0]
    # The same answer for a child that does not exist and one this user may not see.
    raise CoachError(
        ERR_CHILD_NOT_FOUND,
        "Unknown child; use list_children for the children you may coach.",
    )


# -- ids and output -----------------------------------------------------------------


def public_id(uid: str) -> str:
    """An item or subtask uid without ``<host>:<child>:`` (the id the tools use)."""
    return uid.split(":", 2)[2]


def _full_uid(child: CoachChild, public: Any, *, subtask_ok: bool) -> str:
    """The uid of an item (or subtask) id of the tools, for this child only."""
    pattern = _ID if subtask_ok else _APPOINTMENT_ID
    if not isinstance(public, str) or not pattern.fullmatch(public):
        raise CoachError(ERR_INVALID_FORMAT, "The id is not a valid id of this tool")
    return f"{child.host}:{child.child_id}:{public}"


def _public_item(item: Payload | None) -> Payload | None:
    """An item payload with ids instead of uids."""
    if item is None:
        return None
    result = {k: v for k, v in item.items() if k != "uid"}
    result["subtasks"] = [
        {"id": public_id(s["uid"]), **{k: v for k, v in s.items() if k != "uid"}}
        for s in item["subtasks"]
    ]
    return {"id": public_id(item["uid"]), **result}


def _title_of(child: CoachChild, uid: str) -> str:
    """How the logbook names an item: ``Proefwerk Engels`` (no teacher data)."""
    manager = child.manager
    if (item := manager.find_item(child.child_id, uid)) is not None:
        return " ".join(part for part in (item.label, item.subject) if part)
    appointment = manager.find_appointment(child.child_id, uid)
    return appointment.subject if appointment else "huiswerk"


def _appointment_view(
    manager: HomeworkManager, child_id: int, appointment: Any
) -> Payload:
    """One appointment for the schedule: no teachers, no codes."""
    base = appointment_to_dict(manager, child_id, appointment)
    local_start = appointment.start.astimezone(LOCAL_TZ)
    local_end = appointment.end.astimezone(LOCAL_TZ)
    info_type = base["info_type"]
    return {
        "id": public_id(base["uid"]),
        "date": local_start.date().isoformat(),
        "start": None if appointment.all_day else local_start.strftime("%H:%M"),
        "end": None if appointment.all_day else local_end.strftime("%H:%M"),
        "all_day": appointment.all_day,
        "lesson_hour": base["lesson_hour"],
        "subject": base["subject"],
        "location": appointment.location,
        "cancelled": appointment.status in CANCELLED_STATUSES,
        "info_type": info_type,
        "magister_label": magister_label_option(info_type).name if info_type else None,
        "manual_labels": base["manual_labels"],
        "override": base["override"],
    }


# -- tool plumbing ------------------------------------------------------------------


def _date_arg(value: Any) -> date:
    try:
        parsed: date = cv.date(value)
    except probatio.Invalid:
        raise CoachError(ERR_INVALID_FORMAT, "Dates are written YYYY-MM-DD") from None
    return parsed


def _check(validator: Callable[[Any], Any], value: Any) -> Any:
    try:
        return validator(value)
    except probatio.Invalid as err:
        raise CoachError(ERR_INVALID_FORMAT, str(err)) from None


def _label_code(err: LabelError) -> str:
    return ERR_INVALID_FORMAT if err.code in INVALID_INPUT else err.code


class CoachCall:
    """What one tool call works with: the child, the arguments and the context."""

    def __init__(
        self,
        hass: HomeAssistant,
        child: CoachChild,
        args: dict[str, Any],
        context: Context | None,
    ) -> None:
        """Create the call."""
        self.hass = hass
        self.child = child
        self.args = args
        self.context = context

    @property
    def manager(self) -> HomeworkManager:
        """The child's homework manager."""
        return self.child.manager

    @property
    def entity(self) -> MagisterHomeworkTodo:
        """The child's homework to-do entity (the shared business logic)."""
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            TODO_DOMAIN,
            DOMAIN,
            f"{self.child.host}:{self.child.child_id}:homework",
        )
        registered = registry.async_get(entity_id) if entity_id else None
        component = self.hass.data.get(DATA_COMPONENT)
        entity = (
            component.get_entity(entity_id)
            if component
            and entity_id
            and registered is not None
            and registered.config_entry_id == self.child.entry.entry_id
            else None
        )
        if not isinstance(entity, MagisterHomeworkTodo):
            raise CoachError(ERR_NOT_FOUND, "Homework to-do list entity not found")
        return entity

    def uid(self, key: str, *, subtask_ok: bool = False) -> str:
        """The full uid of the item or subtask id in argument ``key``."""
        return _full_uid(self.child, self.args[key], subtask_ok=subtask_ok)

    def log(self, message: str) -> None:
        """Write a logbook entry for a change made by the coach."""
        async_log_entry(
            self.hass,
            LOG_NAME,
            f"AI-coach: {message}",
            DOMAIN,
            self.entity.entity_id,
            self.context,
        )


def _child_field() -> dict[Any, Any]:
    return {
        probatio.Optional(
            "child",
            description=(
                "Id of the child (see list_children). Optional when only one child "
                "is linked to you."
            ),
        ): probatio.Any(str, int)
    }


def _schema(fields: dict[Any, Any]) -> probatio.Schema:
    return probatio.Schema({**_child_field(), **fields})


READ_ONLY = llm.ToolAnnotations(
    read_only=True, destructive=False, idempotent=True, open_world=False
)


def _write(
    *, destructive: bool = False, idempotent: bool = True
) -> llm.ToolAnnotations:
    return llm.ToolAnnotations(
        read_only=False,
        destructive=destructive,
        idempotent=idempotent,
        open_world=False,
    )


class CoachTool(llm.Tool):
    """Base of the tools: validates, resolves the child and maps errors."""

    integration = DOMAIN

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Validate the input, check the access and run the tool."""
        try:
            args = self.parameters(tool_input.tool_args)
        except probatio.Invalid as err:
            return error_result(ERR_INVALID_FORMAT, str(err))
        try:
            children = await async_user_children(hass, llm_context.context)
            if not self.needs_child:
                return llm.ToolResult(data=self.run_children(children))
            child = pick_child(children, args.get("child"))
            return llm.ToolResult(
                data=self.run(CoachCall(hass, child, args, llm_context.context))
            )
        except CoachError as err:
            return error_result(err.code, err.message)
        except LabelError as err:
            return error_result(_label_code(err), f"Cannot do this: {err.code}")
        except HomeworkItemDisabled:
            return error_result(ERR_ITEM_DISABLED, "Restore the Magister label first")
        except HomeworkItemHasSubtasks:
            return error_result(
                ERR_ITEM_HAS_SUBTASKS, "The progress is derived from subtasks"
            )
        except ServiceValidationError:
            return error_result(ERR_ITEM_NOT_FOUND, "Homework item not found")
        except Exception as err:
            _LOGGER.error(
                "The coach tool %s failed unexpectedly (%s)",
                self.name,
                type(err).__name__,
            )
            _LOGGER.debug("Details of the failed coach tool", exc_info=True)
            return error_result(ERR_INTERNAL, "The tool failed; try again later")

    needs_child = True

    def run(self, call: CoachCall) -> Payload:
        """Do the work for an accessible child."""
        raise NotImplementedError  # pragma: no cover

    def run_children(self, children: list[CoachChild]) -> Payload:
        """Do the work for tools that need no child."""
        raise NotImplementedError  # pragma: no cover


# -- read tools ---------------------------------------------------------------------


class ListChildrenTool(CoachTool):
    """``list_children``."""

    name = "list_children"
    description = (
        "List the children you may coach (id and first name). Use the id as `child` "
        "in the other tools."
    )
    parameters = probatio.Schema({})
    annotations = READ_ONLY
    needs_child = False

    def run_children(self, children: list[CoachChild]) -> Payload:
        """The accessible children, or the explanation how to get linked."""
        if not children:
            return {"children": [], "message": NOT_LINKED_HELP}
        return {"children": [{"id": c.id, "name": c.name} for c in children]}


class GetScheduleTool(CoachTool):
    """``get_schedule``."""

    name = "get_schedule"
    description = (
        "The lessons and appointments of a child between two dates (inclusive, at most "
        f"{MAX_SCHEDULE_DAYS} days): date, start and end time, lesson hour, subject, "
        "location, whether it is cancelled, and its labels including overrides. Only "
        "the weeks Home Assistant fetched from Magister are available."
    )
    parameters = _schema(
        {
            probatio.Required("start", description="First day, YYYY-MM-DD"): str,
            probatio.Required("end", description="Last day, YYYY-MM-DD"): str,
        }
    )
    annotations = READ_ONLY

    def run(self, call: CoachCall) -> Payload:
        """The appointments of the days."""
        start, end = _date_arg(call.args["start"]), _date_arg(call.args["end"])
        if end < start or (end - start).days >= MAX_SCHEDULE_DAYS:
            raise CoachError(
                ERR_INVALID_FORMAT,
                f"`end` must not be before `start`, at most {MAX_SCHEDULE_DAYS} days",
            )
        manager = call.manager
        first, after_last = manager.window_dates()
        appointments = []
        day = max(start, first)
        while day <= min(end, after_last - timedelta(days=1)):
            appointments += [
                _appointment_view(manager, call.child.child_id, a)
                for a in manager.appointments_on(call.child.child_id, day)
            ]
            day += timedelta(days=1)
        return {
            "child": call.child.id,
            "available_from": first.isoformat(),
            "available_until": (after_last - timedelta(days=1)).isoformat(),
            "appointments": appointments,
        }


class ListHomeworkTool(CoachTool):
    """``list_homework``."""

    name = "list_homework"
    description = (
        "The homework and tests of a child in the planner, sorted by date, with their "
        "labels, text, due date, progress, whether the progress is derived from "
        "subtasks, and the subtasks (current date, overdue, created_by). By default "
        "from today on and without completed items, plus the open items that are "
        "overdue (due before today; see include_overdue)."
    )
    parameters = _schema(
        {
            probatio.Optional(
                "start", description="First due day, YYYY-MM-DD (default: today)"
            ): str,
            probatio.Optional("end", description="Last due day, YYYY-MM-DD"): str,
            probatio.Optional(
                "include_completed",
                default=False,
                description="Also list completed and disabled items",
            ): bool,
            probatio.Optional(
                "include_overdue",
                default=True,
                description=(
                    "Also list open items due before today (only when `start` is not "
                    "given)"
                ),
            ): bool,
        }
    )
    annotations = READ_ONLY

    def run(self, call: CoachCall) -> Payload:
        """The items in the range."""
        manager = call.manager
        start = _date_arg(call.args["start"]) if "start" in call.args else None
        end = _date_arg(call.args["end"]) if "end" in call.args else None
        today = manager.today()
        overdue = call.args["include_overdue"] and start is None
        first = start or today

        def wanted(item: Any) -> bool:
            if end is not None and item.due_date > end:
                return False
            done = manager.is_completed(item)
            if item.due_date >= first:
                return call.args["include_completed"] or not done
            return bool(overdue) and item.due_date < today and not done

        items = [
            item_to_dict(manager, item)
            for item in manager.items(call.child.child_id)
            if wanted(item)
        ]
        return {
            "child": call.child.id,
            "today": manager.today().isoformat(),
            "items": [_public_item(item) for item in items],
        }


class GetProgressTool(CoachTool):
    """``get_progress``."""

    name = "get_progress"
    description = (
        "The homework progress of a child, as the Home Assistant sensors: next school "
        "day, this week and next week (value 0 to 100, number of items, completed)."
    )
    parameters = _schema({})
    annotations = READ_ONLY

    def run(self, call: CoachCall) -> Payload:
        """The three period values."""
        return {
            "child": call.child.id,
            "today": call.manager.today().isoformat(),
            "progress": progress_payload(
                call.manager, call.child.child_id, available=call.entity.available
            ),
        }


class ListLabelOptionsTool(CoachTool):
    """``list_label_options``."""

    name = "list_label_options"
    description = (
        "The labels a child can get on a lesson (id, name, kind homework or test). "
        "Use the id or the name in add_label and set_label_override."
    )
    parameters = _schema({})
    annotations = READ_ONLY

    def run(self, call: CoachCall) -> Payload:
        """The child's label options."""
        return {
            "child": call.child.id,
            "labels": [
                {"id": o.id, "name": o.name, "kind": o.kind}
                for o in call.manager.label_options(call.child.child_id)
            ],
        }


# -- write tools --------------------------------------------------------------------


class AddSubtaskTool(CoachTool):
    """``add_subtask``."""

    name = "add_subtask"
    description = (
        "Add a subtask (deelstap) to a homework item, planned on a day (default "
        "today). "
        f"The title has 1 to {SUBTASK_TITLE_MAX} characters; at most {MAX_SUBTASKS} "
        "subtasks per item. The subtask is marked as created by the AI."
    )
    parameters = _schema(
        {
            probatio.Required("item", description="Id of the item"): str,
            probatio.Required("title", description="Title of the subtask"): str,
            probatio.Optional("date", description="Planned day, YYYY-MM-DD"): str,
        }
    )
    annotations = _write(idempotent=False)

    def run(self, call: CoachCall) -> Payload:
        """Add the subtask through the entity (same rules as the WebSocket API)."""
        uid = call.uid("item")
        title = _check(subtask_title, call.args["title"])
        planned = _date_arg(call.args["date"]) if "date" in call.args else None
        parent = _title_of(call.child, uid)
        item = call.entity.add_subtask(uid, title, planned, CREATED_BY_AI)
        call.log(f"deelstap '{title}' toegevoegd aan {parent}")
        return {"item": _public_item(item)}


class UpdateSubtaskTool(CoachTool):
    """``update_subtask``."""

    name = "update_subtask"
    description = (
        "Change the title and/or the planned day of a subtask. Give at least one of "
        "`title` and `date`."
    )
    parameters = _schema(
        {
            probatio.Required(
                "subtask", description="Id of the subtask (<item id>:sub:<id>)"
            ): str,
            probatio.Optional("title", description="New title"): str,
            probatio.Optional("date", description="New planned day, YYYY-MM-DD"): str,
        }
    )
    annotations = _write()

    def run(self, call: CoachCall) -> Payload:
        """Change the subtask through the entity."""
        uid = call.uid("subtask", subtask_ok=True)
        title = (
            _check(subtask_title, call.args["title"]) if "title" in call.args else None
        )
        planned = _date_arg(call.args["date"]) if "date" in call.args else None
        before = call.manager.find_subtask(uid)
        was = (before.title, before.planned) if before else None
        parent = _title_of(call.child, uid.split(":sub:")[0])
        item = call.entity.update_subtask(uid, title, planned)
        after = call.manager.find_subtask(uid)
        if after is not None and (after.title, after.planned) != was:
            call.log(f"deelstap '{after.title}' gewijzigd bij {parent}")
        return {"item": _public_item(item)}


class DeleteSubtaskTool(CoachTool):
    """``delete_subtask``."""

    name = "delete_subtask"
    description = (
        "Delete a subtask. Ask the student for permission first. An item without "
        "subtasks uses its own progress again."
    )
    parameters = _schema(
        {
            probatio.Required(
                "subtask", description="Id of the subtask (<item id>:sub:<id>)"
            ): str,
        }
    )
    annotations = _write(destructive=True)

    def run(self, call: CoachCall) -> Payload:
        """Delete the subtask through the entity."""
        uid = call.uid("subtask", subtask_ok=True)
        before = call.manager.find_subtask(uid)
        parent = _title_of(call.child, uid.split(":sub:")[0])
        item = call.entity.delete_subtask(uid)
        call.log(f"deelstap '{before.title if before else ''}' verwijderd bij {parent}")
        return {"item": _public_item(item)}


class SetProgressTool(CoachTool):
    """``set_progress``."""

    name = "set_progress"
    description = (
        "Set the progress (0 to 100; use 0, 25, 50, 75 or 100) of an item without "
        "subtasks, or of a subtask. Only do this when the student confirms."
    )
    parameters = _schema(
        {
            probatio.Required(
                "id", description="Id of the item or of the subtask"
            ): str,
            probatio.Required("progress", description="Percent, 0 to 100"): int,
        }
    )
    annotations = _write()

    def run(self, call: CoachCall) -> Payload:
        """Set the progress through the entity."""
        uid = call.uid("id", subtask_ok=True)
        progress = _check(strict_progress, call.args["progress"])
        entity = call.entity
        previous = entity.stored_progress(uid)
        entity.set_progress(uid, progress)
        stored = entity.stored_progress(uid)
        parent_uid = uid.split(":sub:")[0]
        parent = _title_of(call.child, parent_uid)
        if stored == previous:
            pass  # nothing changed: no logbook entry
        elif (sub := call.manager.find_subtask(uid)) is not None:
            call.log(
                f"voortgang van deelstap '{sub.title}' ({parent}) op {stored}% gezet"
            )
        else:
            call.log(f"voortgang van {parent} op {stored}% gezet")
        item = call.manager.find_item(call.child.child_id, parent_uid)
        return {
            "id": public_id(uid),
            "progress": stored,
            "completed": stored >= 100,
            "item": _public_item(item_to_dict(call.manager, item) if item else None),
        }


class AddLabelTool(CoachTool):
    """``add_label``."""

    name = "add_label"
    description = (
        "Add a manual label (see list_label_options) to a lesson, optionally with a "
        f"short note (at most {NOTE_MAX} characters), for example what to study."
    )
    parameters = _schema(
        {
            probatio.Required("appointment", description="Id of the lesson"): str,
            probatio.Required("label", description="Label id or name"): str,
            probatio.Optional("note", description="Short note"): str,
        }
    )
    annotations = _write()

    def run(self, call: CoachCall) -> Payload:
        """Add the label through the entity."""
        uid = call.uid("appointment")
        note = _check(validate_note, call.args.get("note", ""))
        title = _title_of(call.child, uid)
        entity = call.entity
        label = entity.label_option(call.args["label"], by_name=True)
        item = entity.add_label(uid, label.id, note)
        call.log(f"label '{label.name}' toegevoegd aan {title}")
        return {"item": _public_item(item)}


class RemoveLabelTool(CoachTool):
    """``remove_label``."""

    name = "remove_label"
    description = (
        "Remove a manual label from a lesson. Ask the student for permission first. "
        "Magister's own labels cannot be removed (use set_label_override)."
    )
    parameters = _schema(
        {
            probatio.Required("appointment", description="Id of the lesson"): str,
            probatio.Required("label", description="Label id or name"): str,
        }
    )
    annotations = _write(destructive=True)

    def run(self, call: CoachCall) -> Payload:
        """Remove the label through the entity."""
        uid = call.uid("appointment")
        title = _title_of(call.child, uid)
        entity = call.entity
        label = entity.label_option(call.args["label"], by_name=True)
        item = entity.remove_label(uid, label.id)
        call.log(f"label '{label.name}' verwijderd van {title}")
        return {"item": _public_item(item)}


class SetLabelOverrideTool(CoachTool):
    """``set_label_override``."""

    name = "set_label_override"
    description = (
        "Replace, disable or restore the Magister label of a lesson (Huiswerk, "
        "Proefwerk, ...). `replace` needs `label`; `disable` takes the item out of the "
        "progress; `clear` restores the original label."
    )
    parameters = _schema(
        {
            probatio.Required("appointment", description="Id of the lesson"): str,
            probatio.Required("mode"): probatio.In(
                [MODE_REPLACE, MODE_DISABLE, MODE_CLEAR]
            ),
            probatio.Optional(
                "label", description="Label id or name (for `replace`)"
            ): str,
        }
    )
    annotations = _write()

    def run(self, call: CoachCall) -> Payload:
        """Set the override through the entity."""
        uid = call.uid("appointment")
        mode = call.args["mode"]
        title = _title_of(call.child, uid)
        entity = call.entity
        was = call.manager.stored_override(uid)
        item = entity.set_override(uid, mode, call.args.get("label"), by_name=True)
        if call.manager.stored_override(uid) == was:
            pass  # nothing changed: no logbook entry
        elif mode == MODE_REPLACE:
            label = entity.label_option(call.args["label"], by_name=True)
            call.log(f"Magister-label van {title} vervangen door '{label.name}'")
        elif mode == MODE_DISABLE:
            call.log(f"Magister-label van {title} uitgeschakeld")
        else:
            call.log(f"Magister-label van {title} hersteld")
        return {"item": _public_item(item)}


def coach_tools() -> list[llm.Tool]:
    """All tools of the API."""
    return [
        ListChildrenTool(),
        GetScheduleTool(),
        ListHomeworkTool(),
        GetProgressTool(),
        ListLabelOptionsTool(),
        AddSubtaskTool(),
        UpdateSubtaskTool(),
        DeleteSubtaskTool(),
        SetProgressTool(),
        AddLabelTool(),
        RemoveLabelTool(),
        SetLabelOverrideTool(),
    ]


# -- the API ------------------------------------------------------------------------


def build_prompt(today: date, children: list[CoachChild], time_zone: str) -> str:
    """The prompt sent with the tools: date, rules and the children's guidelines."""
    lines = [
        f"Today is {today.isoformat()} ({today.strftime('%A')}). School time zone: "
        f"{LOCAL_TZ.key}; Home Assistant time zone: {time_zone}.",
        "",
        PLANNER_RULES,
        "",
    ]
    if not children:
        lines.append(NOT_LINKED_HELP + " Until then, no data is available.")
        return "\n".join(lines)
    lines.append(
        "You may coach: " + ", ".join(f"{c.name} (id {c.id})" for c in children) + "."
    )
    if len(children) > 1:
        lines.append("Always pass `child` in the tools.")
    for child in children:
        lines += [
            "",
            f"Coaching guidelines for {child.name} (id {child.id}):",
            child.guidelines,
        ]
    return "\n".join(lines)


class MagisterCoachAPI(llm.API):
    """The LLM API of the AI homework coach."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """The tools and the prompt for the user behind the request."""
        children = await async_user_children(self.hass, llm_context.context)
        today = dt_util.now(LOCAL_TZ).date()
        return llm.APIInstance(
            api=self,
            api_prompt=build_prompt(today, children, self.hass.config.time_zone),
            llm_context=llm_context,
            tools=coach_tools(),
        )


@callback
def async_register_coach_api(hass: HomeAssistant) -> None:
    """Register the API once per Home Assistant run (a second call does nothing)."""
    if _UNREGISTER in hass.data:
        return
    hass.data[_UNREGISTER] = llm.async_register_api(
        hass, MagisterCoachAPI(hass=hass, id=COACH_API_ID, name=COACH_API_NAME)
    )


@callback
def async_unregister_coach_api(hass: HomeAssistant) -> None:
    """Remove the API (the last entry is unloaded)."""
    if (unregister := hass.data.pop(_UNREGISTER, None)) is not None:
        unregister()
