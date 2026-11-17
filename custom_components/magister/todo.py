"""To-do platform for Magister: the homework planner, one list per child."""

from __future__ import annotations

from datetime import date
from typing import Any

import probatio
from homeassistant.components.todo.const import (
    DOMAIN as TODO_DOMAIN,
)
from homeassistant.components.todo.const import TodoItemStatus, TodoListEntityFeature
from homeassistant.components.todo.entity import TodoItem, TodoListEntity
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.util import dt as dt_util

from .api.homework import (
    CREATED_BY_USER,
    MODE_CLEAR,
    MODE_DISABLE,
    MODE_REPLACE,
    HomeworkItem,
    LabelOption,
    Override,
    Subtask,
    find_label_option,
    magister_label_text,
    split_subtask_uid,
    subtask_current_date,
    subtask_uid,
)
from .api.mapping import ATTACHMENTS_LINE, LOCAL_TZ
from .const import (
    ATTR_APPOINTMENT,
    ATTR_DATE,
    ATTR_ITEM,
    ATTR_LABEL,
    ATTR_MINUTES,
    ATTR_MODE,
    ATTR_NOTE,
    ATTR_PROGRESS,
    ATTR_SUBTASK,
    ATTR_TITLE,
    CHILD_ID,
    CHILD_SHORT_NAME,
    CONF_CHILDREN,
    CONF_HOST,
    DOMAIN,
    SERVICE_ADD_HOMEWORK_LABEL,
    SERVICE_ADD_HOMEWORK_SUBTASK,
    SERVICE_DELETE_HOMEWORK_SUBTASK,
    SERVICE_REMOVE_HOMEWORK_LABEL,
    SERVICE_SET_HOMEWORK_OVERRIDE,
    SERVICE_SET_HOMEWORK_PROGRESS,
    SERVICE_UPDATE_HOMEWORK_SUBTASK,
)
from .coordinator import MagisterConfigEntry, MagisterCoordinator
from .entity import MagisterMidnightEntity
from .homework import (
    ERR_LABEL_NOT_FOUND,
    ERR_LABEL_REQUIRED,
    UNSET,
    HomeworkManager,
    LabelError,
    Payload,
    any_value,
    appointment_to_dict,
    async_publish,
    build_payload,
    note_text,
    service_progress,
    subtask_title,
)
from .homework import (
    item_to_dict as item_dict,
)

PARALLEL_UPDATES = 0

type Day = date

CANCELLED_NOTE = "Les vervallen"
SUBTASK_PREFIX = "\u21b3 "


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MagisterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a homework list for each selected child."""
    runtime = entry.runtime_data
    host: str = entry.data[CONF_HOST]
    async_add_entities(
        MagisterHomeworkTodo(
            runtime.coordinator,
            runtime.homework,
            host,
            int(child[CHILD_ID]),
            str(child[CHILD_SHORT_NAME]),
        )
        for child in entry.data[CONF_CHILDREN]
    )


@callback
def async_register_homework_services(hass: HomeAssistant) -> None:
    """Register the homework services (at integration setup)."""
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_HOMEWORK_LABEL,
        entity_domain=TODO_DOMAIN,
        func="async_add_homework_label",
        schema={
            probatio.Required(ATTR_APPOINTMENT): cv.string,
            probatio.Required(ATTR_LABEL): cv.string,
            probatio.Optional(ATTR_NOTE, default=""): note_text,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_REMOVE_HOMEWORK_LABEL,
        entity_domain=TODO_DOMAIN,
        func="async_remove_homework_label",
        schema={
            probatio.Required(ATTR_APPOINTMENT): cv.string,
            probatio.Required(ATTR_LABEL): cv.string,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HOMEWORK_OVERRIDE,
        entity_domain=TODO_DOMAIN,
        func="async_set_homework_override",
        schema={
            probatio.Required(ATTR_APPOINTMENT): cv.string,
            probatio.Required(ATTR_MODE): probatio.In(
                [MODE_REPLACE, MODE_DISABLE, MODE_CLEAR]
            ),
            probatio.Optional(ATTR_LABEL): cv.string,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HOMEWORK_PROGRESS,
        entity_domain=TODO_DOMAIN,
        func="async_set_homework_progress",
        schema={
            probatio.Required(ATTR_ITEM): cv.string,
            probatio.Required(ATTR_PROGRESS): service_progress,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_HOMEWORK_SUBTASK,
        entity_domain=TODO_DOMAIN,
        func="async_add_homework_subtask",
        schema={
            probatio.Required(ATTR_ITEM): cv.string,
            probatio.Required(ATTR_TITLE): subtask_title,
            probatio.Optional(ATTR_DATE): cv.date,
            probatio.Optional(ATTR_MINUTES): any_value,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UPDATE_HOMEWORK_SUBTASK,
        entity_domain=TODO_DOMAIN,
        func="async_update_homework_subtask",
        schema={
            probatio.Required(ATTR_SUBTASK): cv.string,
            probatio.Optional(ATTR_TITLE): subtask_title,
            probatio.Optional(ATTR_DATE): cv.date,
            probatio.Optional(ATTR_MINUTES): any_value,
        },
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_DELETE_HOMEWORK_SUBTASK,
        entity_domain=TODO_DOMAIN,
        func="async_delete_homework_subtask",
        schema={probatio.Required(ATTR_SUBTASK): cv.string},
    )


def item_summary(item: HomeworkItem) -> str:
    """``[Magister label] [manual label] subject``.

    The Magister label follows its override: ``Proefwerk->Huiswerk`` for a
    replacement, nothing when it is disabled.
    """
    magister = magister_label_text(item)
    if magister is None:
        magister = item.label or ""
    names = ([magister] if magister else []) + [
        label.name for label in item.manual_labels
    ]
    return " ".join([*(f"[{name}]" for name in names), item.subject]).rstrip()


def to_subtask_todo_item(item: HomeworkItem, sub: Subtask, today: date) -> TodoItem:
    """The to-do item of a subtask: ``↳ <subject>: <title>``."""
    return TodoItem(
        summary=f"{SUBTASK_PREFIX}{item.subject}: {sub.title}",
        uid=subtask_uid(item.uid, sub.id),
        status=TodoItemStatus.COMPLETED if sub.done else TodoItemStatus.NEEDS_ACTION,
        due=subtask_current_date(sub, item.due_date, today),
        description=f"({sub.progress} %)" if 0 < sub.progress < 100 else None,
    )


def to_todo_items(manager: HomeworkManager, child_id: int) -> list[TodoItem]:
    """The to-do list of a child: each item followed by its subtasks."""
    today = manager.today()
    todo: list[TodoItem] = []
    for item in manager.items(child_id):
        todo.append(to_todo_item(manager, item))
        todo.extend(
            to_subtask_todo_item(item, sub, today)
            for sub in manager.active_subtasks(item)
        )
    return todo


def to_todo_item(manager: HomeworkManager, item: HomeworkItem) -> TodoItem:
    """The to-do item of a homework item (see the milestone spec)."""
    progress = manager.progress(item.uid)
    disabled = manager.effective(item).disabled
    lines = [item.text] if item.text else []
    lines.extend(label.note for label in item.manual_labels if label.note)
    if item.cancelled:
        lines.append(CANCELLED_NOTE)
    if item.has_attachments:
        lines.append(ATTACHMENTS_LINE)
    if 0 < progress < 100 and not disabled:
        lines.append(f"({progress} %)")
    return TodoItem(
        summary=item_summary(item),
        uid=item.uid,
        status=(
            TodoItemStatus.COMPLETED
            if manager.is_completed(item)
            else TodoItemStatus.NEEDS_ACTION
        ),
        due=item.due_date if item.all_day else item.start.astimezone(LOCAL_TZ),
        description="\n".join(lines) or None,
        completed=manager.completed_at(item.uid),
    )


class HomeworkItemHasSubtasks(ServiceValidationError):
    """The item has subtasks: its progress is derived and cannot be set."""

    def __init__(self) -> None:
        """Create the translated error."""
        super().__init__(
            translation_domain=DOMAIN, translation_key="homework_item_has_subtasks"
        )


class HomeworkItemDisabled(ServiceValidationError):
    """The item's Magister label is disabled: restore it before changing progress."""

    def __init__(self) -> None:
        """Create the translated error."""
        super().__init__(
            translation_domain=DOMAIN, translation_key="homework_item_disabled"
        )


def _label_exception(err: LabelError) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN, translation_key=f"homework_{err.code}"
    )


class MagisterHomeworkTodo(MagisterMidnightEntity, TodoListEntity):
    """The homework and tests of one child."""

    _attr_translation_key = "homework"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(
        self,
        coordinator: MagisterCoordinator,
        manager: HomeworkManager,
        host: str,
        child_id: int,
        short_name: str,
    ) -> None:
        """Create the list."""
        super().__init__(coordinator, host, child_id, short_name)
        self._manager = manager
        self._attr_unique_id = f"{host}:{child_id}:homework"
        self._last_payload: Payload | None = None
        self._rebuild()

    @property
    def state(self) -> int | None:
        """The open items due today or later.

        HA counts every ``needs_action`` item; past homework stays in the list but
        is not counted. Recomputed on each state write, including at midnight.
        """
        return self._manager.due_open_count(
            self._child_id, dt_util.now(LOCAL_TZ).date()
        )

    @callback
    def _rebuild(self) -> None:
        self._attr_todo_items = to_todo_items(self._manager, self._child_id)

    async def async_added_to_hass(self) -> None:
        """Follow progress changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.async_add_listener(self._handle_progress))
        self._start_midnight()

    @callback
    def _handle_progress(self) -> None:
        self._rebuild()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._rebuild()
        super()._handle_coordinator_update()

    @callback
    def _on_new_day(self) -> None:
        """Subtasks roll over: new due dates, a new payload and a new count."""
        self._manager.async_expire_proposals()
        self._rebuild()
        super()._on_new_day()

    @callback
    def _async_write_ha_state(self) -> None:
        """Push the list to the WebSocket subscribers of the card as well."""
        super()._async_write_ha_state()
        payload = build_payload(self._manager, self._child_id, available=self.available)
        if payload != self._last_payload:
            self._last_payload = payload
            async_publish(self.hass, self.entity_id, payload)

    async def async_will_remove_from_hass(self) -> None:
        """Tell the card that the list is gone (the last items stay in the payload)."""
        items = self._last_payload["items"] if self._last_payload else []
        labels = self._last_payload["labels"] if self._last_payload else []
        async_publish(
            self.hass,
            self.entity_id,
            {
                "available": False,
                "items": items,
                "labels": labels,
                "progress": {"next_day": None, "week": None, "next_week": None},
                "daily_max_minutes": self._manager.daily_max(self._child_id),
                "daily_max_weekdays": list(
                    self._manager.daily_max_weekdays(self._child_id)
                ),
                "proposals": (
                    self._last_payload["proposals"] if self._last_payload else []
                ),
                "daily_max_overrides": (
                    self._last_payload["daily_max_overrides"]
                    if self._last_payload
                    else {}
                ),
            },
        )
        await super().async_will_remove_from_hass()

    async def respond_proposal(
        self,
        proposal_id: str,
        answer: str,
        *,
        user_id: str | None,
        user_name: str | None,
        is_admin: bool,
        context: Context | None,
    ) -> Payload:
        """Answer a proposal for the daily maximum as this user (rights checked)."""
        proposal = await self._manager.answer_proposal(
            self._child_id,
            proposal_id,
            answer,
            user_id=user_id,
            user_name=user_name,
            is_admin=is_admin,
            context=context,
        )
        return proposal.view(dt_util.utcnow())

    @callback
    def payload(self) -> Payload:
        """The current list for a new WebSocket subscriber."""
        return build_payload(self._manager, self._child_id, available=self.available)

    def _require_item(self, uid: str) -> HomeworkItem:
        item = self._manager.find_item(self._child_id, uid)
        if item is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="homework_item_not_found"
            )
        return item

    def _require_enabled(self, uid: str) -> HomeworkItem:
        """The item (or the parent of a subtask uid): it must exist and not be disabled.

        A subtask uid must also name an existing (visible) subtask; an item with
        subtasks is refused as ``HomeworkItemHasSubtasks`` unless ``uid`` is a subtask.
        """
        ref = split_subtask_uid(uid)
        item = self._require_item(ref[0] if ref else uid)
        if self._manager.effective(item).disabled:
            raise HomeworkItemDisabled
        if ref is not None:
            if self._manager.find_subtask(uid) is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="homework_item_not_found",
                )
        elif self._manager.has_subtasks(uid):
            raise HomeworkItemHasSubtasks
        return item

    @callback
    def set_progress(self, uid: str, progress: int) -> None:
        """Set the progress (0-100) of one of this child's items or subtasks."""
        self._require_enabled(uid)
        self._manager.set_progress(uid, progress)

    @callback
    def add_subtask(
        self,
        item: str,
        title: str,
        planned: Day | None,
        created_by: str = CREATED_BY_USER,
        minutes: Any = None,
    ) -> Payload:
        """Add a subtask; returns the updated item (``LabelError`` on failure)."""
        parent = self._manager.add_subtask(
            self._child_id, item, title, planned, created_by, minutes
        )
        return item_dict(self._manager, parent)

    @callback
    def update_subtask(
        self,
        subtask: str,
        title: str | None,
        planned: Day | None,
        minutes: Any = UNSET,
    ) -> Payload:
        """Change a subtask's title, date and/or time; returns the updated item."""
        parent = self._manager.update_subtask(
            self._child_id, subtask, title, planned, minutes
        )
        return item_dict(self._manager, parent)

    @callback
    def delete_subtask(self, subtask: str) -> Payload:
        """Delete a subtask; returns the updated item."""
        parent = self._manager.delete_subtask(self._child_id, subtask)
        return item_dict(self._manager, parent)

    @callback
    def stored_progress(self, uid: str) -> int:
        """The stored progress of an item."""
        return self._manager.progress(uid)

    def label_option(self, reference: str, *, by_name: bool = False) -> LabelOption:
        """The label option of this child by id (or name), else ``label_not_found``."""
        option = find_label_option(
            self._manager.label_options(self._child_id), reference, by_name=by_name
        )
        if option is None:
            raise LabelError(ERR_LABEL_NOT_FOUND)
        return option

    @callback
    def add_label(
        self, appointment: str, label: str, note: str, *, by_name: bool = False
    ) -> Payload:
        """Add a manual label; returns the updated item (``LabelError`` on failure)."""
        option = self.label_option(label, by_name=by_name)
        item = self._manager.add_label(self._child_id, appointment, option, note)
        return item_dict(self._manager, item)

    @callback
    def remove_label(
        self, appointment: str, label: str, *, by_name: bool = False
    ) -> Payload | None:
        """Remove a manual label; ``None`` when the item left the planner."""
        option = self.label_option(label, by_name=by_name)
        item = self._manager.remove_label(self._child_id, appointment, option)
        return item_dict(self._manager, item) if item else None

    @callback
    def set_override(
        self, appointment: str, mode: str, label: str | None, *, by_name: bool = False
    ) -> Payload | None:
        """Replace, disable or restore the label; returns the item or ``None``."""
        override: Override | None = None
        if mode == MODE_REPLACE:
            if label is None:
                raise LabelError(ERR_LABEL_REQUIRED)
            override = Override(MODE_REPLACE, self.label_option(label, by_name=by_name))
        elif mode == MODE_DISABLE:
            override = Override(MODE_DISABLE)
        item = self._manager.set_override(self._child_id, appointment, override)
        return item_dict(self._manager, item) if item else None

    @callback
    def appointments(self, day: date) -> list[Payload]:
        """The appointments of a day, with their labels."""
        return [
            appointment_to_dict(self._manager, self._child_id, appointment)
            for appointment in self._manager.appointments_on(self._child_id, day)
        ]

    @callback
    def in_window(self, day: date) -> bool:
        """Whether ``day`` lies within the fetch window."""
        first, end = self._manager.window_dates()
        return first <= day < end

    async def async_add_homework_label(
        self, appointment: str, label: str, note: str = ""
    ) -> None:
        """Service ``magister.add_homework_label``."""
        try:
            self.add_label(appointment, label, note, by_name=True)
        except LabelError as err:
            raise _label_exception(err) from None

    async def async_remove_homework_label(self, appointment: str, label: str) -> None:
        """Service ``magister.remove_homework_label``."""
        try:
            self.remove_label(appointment, label, by_name=True)
        except LabelError as err:
            raise _label_exception(err) from None

    async def async_set_homework_override(
        self, appointment: str, mode: str, label: str | None = None
    ) -> None:
        """Service ``magister.set_homework_override``."""
        try:
            self.set_override(appointment, mode, label, by_name=True)
        except LabelError as err:
            raise _label_exception(err) from None

    async def async_add_homework_subtask(
        self,
        item: str,
        title: str,
        date: Day | None = None,
        minutes: Any = None,
    ) -> None:
        """Service ``magister.add_homework_subtask``."""
        try:
            self.add_subtask(item, title, date, minutes=minutes)
        except LabelError as err:
            raise _label_exception(err) from None

    async def async_update_homework_subtask(
        self,
        subtask: str,
        title: str | None = None,
        date: Day | None = None,
        minutes: Any = UNSET,
    ) -> None:
        """Service ``magister.update_homework_subtask``."""
        try:
            self.update_subtask(subtask, title, date, minutes)
        except LabelError as err:
            raise _label_exception(err) from None

    async def async_delete_homework_subtask(self, subtask: str) -> None:
        """Service ``magister.delete_homework_subtask``."""
        try:
            self.delete_subtask(subtask)
        except LabelError as err:
            raise _label_exception(err) from None

    async def async_set_homework_progress(self, item: str, progress: int) -> None:
        """Service ``magister.set_homework_progress``."""
        self.set_progress(item, progress)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Tick (100 %) or untick (the last progress below 100) an item.

        Only the status can be changed; the items come from Magister.
        """
        uid = item.uid or ""
        self._require_enabled(uid)
        current = next((i for i in self._attr_todo_items or [] if i.uid == uid), None)
        if current is not None and (
            item.summary != current.summary
            or item.description != current.description
            or item.due != current.due
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="homework_status_only"
            )
        if item.status == TodoItemStatus.COMPLETED:
            self._manager.set_progress(uid, 100)
        elif item.status == TodoItemStatus.NEEDS_ACTION:
            self._manager.reopen(uid)
