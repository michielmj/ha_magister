"""To-do platform for Magister: the homework planner, one list per child."""

from __future__ import annotations

import probatio
from homeassistant.components.todo.const import TodoItemStatus, TodoListEntityFeature
from homeassistant.components.todo.entity import TodoItem, TodoListEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)

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
    async_get_current_platform().async_register_entity_service(
        SERVICE_SET_HOMEWORK_PROGRESS,
        {
            probatio.Required(ATTR_ITEM): cv.string,
            probatio.Required(ATTR_PROGRESS): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            ),
        },
        "async_set_homework_progress",
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
        self._rebuild()

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

    async def async_set_homework_progress(self, item: str, progress: int) -> None:
        """Service ``magister.set_homework_progress``."""
        self.set_progress(item, progress)

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Tick (100 %) or untick (the last progress below 100) an item.

        Only the status can be changed; the items come from Magister.
        """
        uid = item.uid or ""
        self._require_item(uid)
        if item.status == TodoItemStatus.COMPLETED:
            self._manager.set_progress(uid, 100)
        elif item.status == TodoItemStatus.NEEDS_ACTION:
            self._manager.reopen(uid)
