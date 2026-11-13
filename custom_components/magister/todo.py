"""To-do platform for Magister: the homework planner, one list per child."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import probatio
from homeassistant.components.todo.const import (
    DOMAIN as TODO_DOMAIN,
)
from homeassistant.components.todo.const import TodoItemStatus, TodoListEntityFeature
from homeassistant.components.todo.entity import TodoItem, TodoListEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.util import dt as dt_util

from .api.homework import HomeworkItem
from .api.mapping import ATTACHMENTS_LINE, LOCAL_TZ
from .const import (
    ATTR_ITEM,
    ATTR_PROGRESS,
    CHILD_ID,
    CHILD_SHORT_NAME,
    CONF_CHILDREN,
    CONF_HOST,
    DOMAIN,
    SERVICE_SET_HOMEWORK_PROGRESS,
)
from .coordinator import MagisterConfigEntry, MagisterCoordinator
from .entity import MagisterEntity
from .homework import (
    HomeworkManager,
    Payload,
    async_publish,
    build_payload,
    progress_payload,
    service_progress,
)

PARALLEL_UPDATES = 0

CANCELLED_NOTE = "Les vervallen"


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
def async_register_homework_service(hass: HomeAssistant) -> None:
    """Register ``magister.set_homework_progress`` (at integration setup)."""
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


def to_todo_item(manager: HomeworkManager, item: HomeworkItem) -> TodoItem:
    """The to-do item of a homework item (see the milestone spec)."""
    progress = manager.progress(item.uid)
    lines = [item.text] if item.text else []
    if item.cancelled:
        lines.append(CANCELLED_NOTE)
    if item.has_attachments:
        lines.append(ATTACHMENTS_LINE)
    if 0 < progress < 100:
        lines.append(f"({progress} %)")
    return TodoItem(
        summary=f"[{item.label}] {item.subject}".rstrip(),
        uid=item.uid,
        status=(
            TodoItemStatus.COMPLETED if progress >= 100 else TodoItemStatus.NEEDS_ACTION
        ),
        due=item.due_date if item.all_day else item.start.astimezone(LOCAL_TZ),
        description="\n".join(lines) or None,
        completed=manager.completed_at(item.uid),
    )


class MagisterHomeworkTodo(MagisterEntity, TodoListEntity):
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
        self._unsub_midnight: CALLBACK_TYPE | None = None
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
        self._attr_todo_items = [
            to_todo_item(self._manager, item)
            for item in self._manager.items(self._child_id)
        ]

    async def async_added_to_hass(self) -> None:
        """Follow progress changes."""
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.async_add_listener(self._handle_progress))
        self._schedule_midnight()
        self.async_on_remove(self._cancel_midnight)

    @callback
    def _schedule_midnight(self) -> None:
        tomorrow = dt_util.now(LOCAL_TZ).date() + timedelta(days=1)
        self._unsub_midnight = async_track_point_in_time(
            self.hass,
            self._handle_midnight,
            datetime.combine(tomorrow, time.min, LOCAL_TZ),
        )

    @callback
    def _cancel_midnight(self) -> None:
        if self._unsub_midnight is not None:
            self._unsub_midnight()
            self._unsub_midnight = None

    @callback
    def _handle_midnight(self, _now: datetime) -> None:
        """A new day: the count and the progress periods move on."""
        self.async_write_ha_state()
        self._schedule_midnight()

    @callback
    def _handle_progress(self) -> None:
        self._rebuild()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._rebuild()
        super()._handle_coordinator_update()

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
        async_publish(
            self.hass,
            self.entity_id,
            {
                "available": False,
                "items": items,
                "progress": progress_payload(
                    self._manager, self._child_id, available=False
                ),
            },
        )
        await super().async_will_remove_from_hass()

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

    @callback
    def set_progress(self, uid: str, progress: int) -> None:
        """Set the progress (0-100) of one of this child's items."""
        self._require_item(uid)
        self._manager.set_progress(uid, progress)

    @callback
    def stored_progress(self, uid: str) -> int:
        """The stored progress of an item."""
        return self._manager.progress(uid)

    async def async_set_homework_progress(self, item: str, progress: int) -> None:
        """Service ``magister.set_homework_progress``."""
        self.set_progress(item, progress)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Tick (100 %) or untick (the last progress below 100) an item.

        Only the status can be changed; the items come from Magister.
        """
        uid = item.uid or ""
        self._require_item(uid)
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
