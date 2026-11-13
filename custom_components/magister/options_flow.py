"""Options flow: children, time window and refresh interval."""

from __future__ import annotations

import logging
from typing import Any

import probatio
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import MagisterApiError, MagisterAuthError, MagisterConnectionError, Person
from .const import (
    CHILD_ID,
    CHILD_NAME,
    CHILD_SHORT_NAME,
    CONF_CHILDREN,
    CONF_INTERVAL,
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
    INTERVAL_MAX,
    INTERVAL_MIN,
    INTERVAL_MINUTES,
    WEEKS_AHEAD,
    WEEKS_AHEAD_MAX,
    WEEKS_BACK,
    WEEKS_BACK_MAX,
)
from .pending import peek_retained_login

_LOGGER = logging.getLogger(__name__)


def child_entry(person: Person) -> dict[str, Any]:
    """The stored form of a child in the config entry data."""
    return {
        CHILD_ID: person.id,
        CHILD_NAME: person.name,
        CHILD_SHORT_NAME: person.first_name or person.initials or person.name,
    }


def _number(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
        )
    )


class MagisterOptionsFlow(OptionsFlow):
    """Change the children, the time window and the refresh interval."""

    def __init__(self) -> None:
        """Initialise the flow."""
        self._children: dict[int, dict[str, Any]] | None = None

    async def _async_fetch_children(self, entry: ConfigEntry) -> str | None:
        """Read the current children list; return an abort reason on failure.

        Reuses the entry's kept login, so no password is sent when a token or a
        silent renewal is available.
        """
        login = peek_retained_login(self.hass, entry.entry_id)
        if login is None:
            return "cannot_connect"
        try:
            account = await login.client.async_get_account()
            persons = (
                await login.client.async_get_children(account.person.id)
                if account.is_parent
                else [account.person]
            )
        except MagisterAuthError as err:
            _LOGGER.debug("Options: login failed (%s)", err.code)
            return "auth_failed"
        except (MagisterConnectionError, MagisterApiError) as err:
            _LOGGER.debug("Options: could not read the children: %s", err)
            return "cannot_connect"
        # Children that were selected earlier stay selectable, even when Magister
        # no longer lists them, so they can still be removed.
        children = {int(c[CHILD_ID]): dict(c) for c in entry.data[CONF_CHILDREN]}
        for person in persons:
            children[person.id] = child_entry(person)
        self._children = children
        return None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the options."""
        entry = self.config_entry
        if self._children is None and (
            reason := await self._async_fetch_children(entry)
        ):
            return self.async_abort(reason=reason)
        assert self._children is not None
        errors: dict[str, str] = {}
        current = [int(c[CHILD_ID]) for c in entry.data[CONF_CHILDREN]]
        if user_input is not None:
            selected = {int(value) for value in user_input[CONF_CHILDREN]}
            if not selected:
                errors["base"] = "no_children_selected"
            else:
                options = {
                    CONF_WEEKS_BACK: int(user_input[CONF_WEEKS_BACK]),
                    CONF_WEEKS_AHEAD: int(user_input[CONF_WEEKS_AHEAD]),
                    CONF_INTERVAL: int(user_input[CONF_INTERVAL]),
                }
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_CHILDREN: [
                            child
                            for child_id, child in self._children.items()
                            if child_id in selected
                        ],
                    },
                    options=options,
                )
                return self.async_create_entry(data=options)
        values = user_input or {
            CONF_CHILDREN: [str(child_id) for child_id in current],
            CONF_WEEKS_BACK: entry.options.get(CONF_WEEKS_BACK, WEEKS_BACK),
            CONF_WEEKS_AHEAD: entry.options.get(CONF_WEEKS_AHEAD, WEEKS_AHEAD),
            CONF_INTERVAL: entry.options.get(CONF_INTERVAL, INTERVAL_MINUTES),
        }
        schema = probatio.Schema(
            {
                probatio.Required(CONF_CHILDREN): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=str(child_id), label=str(child[CHILD_NAME])
                            )
                            for child_id, child in self._children.items()
                        ],
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                probatio.Required(CONF_WEEKS_BACK): _number(0, WEEKS_BACK_MAX),
                probatio.Required(CONF_WEEKS_AHEAD): _number(1, WEEKS_AHEAD_MAX),
                probatio.Required(CONF_INTERVAL): _number(INTERVAL_MIN, INTERVAL_MAX),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, values),
            errors=errors,
        )
