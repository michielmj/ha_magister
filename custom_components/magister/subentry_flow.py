"""Sub-entry flow for first-appointment sensors."""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant.config_entries import (
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CHILD_ID,
    CHILD_NAME,
    CONF_CHILD_ID,
    CONF_CHILDREN,
    CONF_EXCLUDED,
    CONF_OFFSET,
    CONF_WEEKS_AHEAD,
    OFFSET_FIELD_MAX,
    WEEKS_AHEAD,
    max_offset,
)

CONF_NAME = "name"


def default_title(offset: int, language: str) -> str:
    """Default sensor name for a day offset (Dutch for ``nl``, else English)."""
    if language.lower().startswith("nl"):
        if offset == 0:
            return "Eerste afspraak vandaag"
        if offset == 1:
            return "Eerste afspraak morgen"
        return f"Eerste afspraak over {offset} dagen"
    if offset == 0:
        return "First appointment today"
    if offset == 1:
        return "First appointment tomorrow"
    return f"First appointment in {offset} days"


class FirstAppointmentSubentryFlow(ConfigSubentryFlow):
    """Add or edit a sensor with the start of the first appointment of a day."""

    def __init__(self) -> None:
        """Initialise the flow."""
        self._child_id: int | None = None
        self._offset = 0
        self._name = ""

    # -------------------------------------------------------------- steps

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the child and the day offset."""
        return await self._async_day_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change the day offset (the child stays) and the name."""
        return await self._async_day_step("reconfigure", user_input)

    async def _async_day_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        entry = self._get_entry()
        reconfigure = step_id == "reconfigure"
        limit = max_offset(int(entry.options.get(CONF_WEEKS_AHEAD, WEEKS_AHEAD)))
        errors: dict[str, str] = {}
        if user_input is not None:
            offset = int(user_input[CONF_OFFSET])
            if offset > limit:
                errors[CONF_OFFSET] = "offset_outside_window"
            else:
                if not reconfigure:
                    self._child_id = int(user_input[CONF_CHILD_ID])
                else:
                    self._child_id = int(
                        self._get_reconfigure_subentry().data[CONF_CHILD_ID]
                    )
                self._offset = offset
                self._name = str(user_input.get(CONF_NAME) or "").strip()
                return await self.async_step_excluded()

        fields: dict[Any, Any] = {}
        suggested: dict[str, Any] = {}
        if not reconfigure:
            fields[probatio.Required(CONF_CHILD_ID)] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(
                            value=str(child[CHILD_ID]), label=str(child[CHILD_NAME])
                        )
                        for child in entry.data[CONF_CHILDREN]
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            subentry = self._get_reconfigure_subentry()
            suggested = {
                CONF_OFFSET: subentry.data[CONF_OFFSET],
                CONF_NAME: subentry.title,
            }
        fields[probatio.Required(CONF_OFFSET, default=0)] = NumberSelector(
            NumberSelectorConfig(
                min=0, max=OFFSET_FIELD_MAX, step=1, mode=NumberSelectorMode.BOX
            )
        )
        fields[probatio.Optional(CONF_NAME)] = TextSelector()
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(fields), user_input or suggested
            ),
            errors=errors,
            description_placeholders={"max_offset": str(limit)},
        )

    async def async_step_excluded(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose the subjects that do not count as first appointment."""
        assert self._child_id is not None
        entry = self._get_entry()
        reconfigure = self.source != "user"
        if user_input is not None:
            excluded = [str(item).strip() for item in user_input[CONF_EXCLUDED]]
            data = {
                CONF_CHILD_ID: self._child_id,
                CONF_OFFSET: self._offset,
                CONF_EXCLUDED: [item for item in excluded if item],
            }
            if reconfigure:
                subentry = self._get_reconfigure_subentry()
                return self.async_update_and_abort(
                    entry, subentry, title=self._reconfigured_title(subentry), data=data
                )
            title = self._name or default_title(self._offset, self.hass.config.language)
            return self.async_create_entry(title=title, data=data)

        known = self._known_subjects(entry)
        current: list[str] = (
            list(self._get_reconfigure_subentry().data[CONF_EXCLUDED])
            if reconfigure
            else []
        )
        subjects = sorted({*known, *current}, key=str.casefold)
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_EXCLUDED, default=current): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=item, label=item)
                            for item in subjects
                        ],
                        multiple=True,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="excluded", data_schema=schema)

    def _reconfigured_title(self, subentry: ConfigSubentry) -> str:
        """Keep a custom title; follow the new offset while the title is the default."""
        old = subentry.title
        if self._name and self._name != old:
            return self._name
        old_offset = int(subentry.data[CONF_OFFSET])
        if old in {default_title(old_offset, "nl"), default_title(old_offset, "en")}:
            return default_title(self._offset, self.hass.config.language)
        return old

    def _known_subjects(self, entry: Any) -> set[str]:
        """Subjects in the child's current data (empty while the entry is down)."""
        try:
            data = entry.runtime_data.coordinator.data or {}
        except AttributeError:
            return set()
        return {item.subject for item in data.get(self._child_id, []) if item.subject}
