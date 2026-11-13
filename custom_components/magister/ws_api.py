"""WebSocket API of the homework planner (used by the Homework planner card).

Commands (any authenticated user, like HA's own ``todo/item/*``):

* ``magister/homework/subscribe``: ``{"entity_id": "todo.xxx"}``. Answers with a result
  and then pushes the full list as events (first right away, then on every change).
* ``magister/homework/set_progress``: ``{"entity_id", "item", "progress"}``.
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

from .homework import async_subscribe, strict_progress
from .todo import MagisterHomeworkTodo

SUBSCRIBE = "magister/homework/subscribe"
SET_PROGRESS = "magister/homework/set_progress"

ERR_NOT_FOUND = "not_found"
ERR_ITEM_NOT_FOUND = "item_not_found"


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the commands (once per Home Assistant run)."""
    async_register_command(hass, websocket_subscribe)
    async_register_command(hass, websocket_set_progress)


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
    except ServiceValidationError:
        connection.send_error(msg["id"], ERR_ITEM_NOT_FOUND, "Homework item not found")
        return
    stored = entity.stored_progress(msg["item"])
    connection.send_result(msg["id"], {"progress": stored, "completed": stored >= 100})
