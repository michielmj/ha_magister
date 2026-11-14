"""WebSocket API of the homework planner (used by the Homework planner card).

Commands (any authenticated user, like HA's own ``todo/item/*``):

* ``magister/homework/subscribe``: ``{"entity_id": "todo.xxx"}``. Answers with a result
  and then pushes the full list as events (first right away, then on every change).
* ``magister/homework/set_progress``: ``{"entity_id", "item", "progress"}``.
* ``magister/homework/appointments``: ``{"entity_id", "date"}`` (read permission).
* ``magister/homework/add_label``: ``{"entity_id", "appointment", "label", "note"?}``.
* ``magister/homework/remove_label``: ``{"entity_id", "appointment", "label"}``.
* ``magister/homework/set_override``: ``{"entity_id", "appointment", "mode", "label"?}``
  with mode ``replace`` (needs a label), ``disable`` or ``clear``.

The label and override commands need control permission.
See docs/reference/homework-websocket.md.
"""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components.todo.const import DATA_COMPONENT
from homeassistant.components.todo.const import DOMAIN as TODO_DOMAIN
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.components.websocket_api.messages import event_message
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv

from .api.homework import MODE_CLEAR, MODE_DISABLE, MODE_REPLACE
from .homework import (
    ERR_INVALID_DATE,
    ERR_LABEL_IS_ORIGINAL,
    ERR_LABEL_REQUIRED,
    LabelError,
    async_subscribe,
    note_text,
    strict_progress,
)
from .todo import HomeworkItemDisabled, MagisterHomeworkTodo

SUBSCRIBE = "magister/homework/subscribe"
SET_PROGRESS = "magister/homework/set_progress"
APPOINTMENTS = "magister/homework/appointments"
ADD_LABEL = "magister/homework/add_label"
REMOVE_LABEL = "magister/homework/remove_label"
SET_OVERRIDE = "magister/homework/set_override"

ERR_NOT_FOUND = "not_found"
ERR_ITEM_NOT_FOUND = "item_not_found"
ERR_ITEM_DISABLED = "item_disabled"
ERR_INVALID_FORMAT = "invalid_format"
INVALID_INPUT = frozenset({ERR_LABEL_REQUIRED, ERR_LABEL_IS_ORIGINAL})


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the commands (once per Home Assistant run)."""
    async_register_command(hass, websocket_subscribe)
    async_register_command(hass, websocket_set_progress)
    async_register_command(hass, websocket_appointments)
    async_register_command(hass, websocket_add_label)
    async_register_command(hass, websocket_remove_label)
    async_register_command(hass, websocket_set_override)


@callback
def _homework_entity(
    hass: HomeAssistant, entity_id: str
) -> MagisterHomeworkTodo | None:
    component = hass.data.get(DATA_COMPONENT)
    entity = component.get_entity(entity_id) if component else None
    return entity if isinstance(entity, MagisterHomeworkTodo) else None


@websocket_command(
    {
        probatio.Required("type"): SUBSCRIBE,
        probatio.Required("entity_id"): cv.entity_domain(TODO_DOMAIN),
    }
)
@callback
def websocket_subscribe(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send the homework list now and push it again on every change."""
    entity_id: str = msg["entity_id"]
    entity = _homework_entity(hass, entity_id)
    if entity is None:
        connection.send_error(
            msg["id"], ERR_NOT_FOUND, "Homework to-do list entity not found"
        )
        return
    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        raise Unauthorized(entity_id=entity_id)

    @callback
    def push(payload: dict[str, Any]) -> None:
        connection.send_message(event_message(msg["id"], payload))

    connection.subscriptions[msg["id"]] = async_subscribe(hass, entity_id, push)
    connection.send_result(msg["id"])
    push(entity.payload())


@websocket_command(
    {
        probatio.Required("type"): SET_PROGRESS,
        probatio.Required("entity_id"): cv.entity_domain(TODO_DOMAIN),
        probatio.Required("item"): cv.string,
        probatio.Required("progress"): strict_progress,
    }
)
@callback
def websocket_set_progress(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Set the progress of one item of the child's list."""
    entity = _homework_entity(hass, msg["entity_id"])
    if entity is None:
        connection.send_error(
            msg["id"], ERR_NOT_FOUND, "Homework to-do list entity not found"
        )
        return
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL):
        raise Unauthorized(entity_id=msg["entity_id"])
    try:
        entity.set_progress(msg["item"], msg["progress"])
    except HomeworkItemDisabled:
        connection.send_error(
            msg["id"], ERR_ITEM_DISABLED, "Restore the Magister label first"
        )
        return
    except ServiceValidationError:
        connection.send_error(msg["id"], ERR_ITEM_NOT_FOUND, "Homework item not found")
        return
    stored = entity.stored_progress(msg["item"])
    connection.send_result(msg["id"], {"progress": stored, "completed": stored >= 100})


@websocket_command(
    {
        probatio.Required("type"): APPOINTMENTS,
        probatio.Required("entity_id"): cv.entity_domain(TODO_DOMAIN),
        probatio.Required("date"): cv.date,
    }
)
@callback
def websocket_appointments(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """List one day's appointments, including those without a label."""
    entity = _homework_entity(hass, msg["entity_id"])
    if entity is None:
        connection.send_error(
            msg["id"], ERR_NOT_FOUND, "Homework to-do list entity not found"
        )
        return
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_READ):
        raise Unauthorized(entity_id=msg["entity_id"])
    if not entity.in_window(msg["date"]):
        connection.send_error(
            msg["id"], ERR_INVALID_DATE, "The date is outside the fetched window"
        )
        return
    connection.send_result(
        msg["id"], {"appointments": entity.appointments(msg["date"])}
    )


@websocket_command(
    {
        probatio.Required("type"): ADD_LABEL,
        probatio.Required("entity_id"): cv.entity_domain(TODO_DOMAIN),
        probatio.Required("appointment"): cv.string,
        probatio.Required("label"): cv.string,
        probatio.Optional("note", default=""): note_text,
    }
)
@callback
def websocket_add_label(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a manual label to an appointment."""
    entity = _controlled_entity(hass, connection, msg)
    if entity is None:
        return
    try:
        item = entity.add_label(msg["appointment"], msg["label"], msg["note"])
    except LabelError as err:
        connection.send_error(msg["id"], err.code, f"Cannot add the label: {err.code}")
        return
    connection.send_result(msg["id"], item)


@websocket_command(
    {
        probatio.Required("type"): REMOVE_LABEL,
        probatio.Required("entity_id"): cv.entity_domain(TODO_DOMAIN),
        probatio.Required("appointment"): cv.string,
        probatio.Required("label"): cv.string,
    }
)
@callback
def websocket_remove_label(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Remove a manual label from an appointment."""
    entity = _controlled_entity(hass, connection, msg)
    if entity is None:
        return
    try:
        item = entity.remove_label(msg["appointment"], msg["label"])
    except LabelError as err:
        connection.send_error(
            msg["id"], err.code, f"Cannot remove the label: {err.code}"
        )
        return
    connection.send_result(msg["id"], {"item": item})


@websocket_command(
    {
        probatio.Required("type"): SET_OVERRIDE,
        probatio.Required("entity_id"): cv.entity_domain(TODO_DOMAIN),
        probatio.Required("appointment"): cv.string,
        probatio.Required("mode"): probatio.In(
            [MODE_REPLACE, MODE_DISABLE, MODE_CLEAR]
        ),
        probatio.Optional("label"): cv.string,
    }
)
@callback
def websocket_set_override(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Replace, disable or restore the Magister label of an appointment."""
    entity = _controlled_entity(hass, connection, msg)
    if entity is None:
        return
    try:
        item = entity.set_override(msg["appointment"], msg["mode"], msg.get("label"))
    except LabelError as err:
        code = ERR_INVALID_FORMAT if err.code in INVALID_INPUT else err.code
        connection.send_error(msg["id"], code, f"Cannot set the override: {err.code}")
        return
    connection.send_result(msg["id"], {"item": item})


@callback
def _controlled_entity(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> MagisterHomeworkTodo | None:
    """The entity of a command that needs control permission (error sent if none)."""
    entity = _homework_entity(hass, msg["entity_id"])
    if entity is None:
        connection.send_error(
            msg["id"], ERR_NOT_FOUND, "Homework to-do list entity not found"
        )
        return None
    if not connection.user.permissions.check_entity(msg["entity_id"], POLICY_CONTROL):
        raise Unauthorized(entity_id=msg["entity_id"])
    return entity
