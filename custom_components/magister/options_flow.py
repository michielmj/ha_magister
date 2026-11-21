"""Options flow: children, time window, refresh interval, weights and labels."""

from __future__ import annotations

import logging
from typing import Any

import probatio
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .api import MagisterApiError, MagisterAuthError, MagisterConnectionError, Person
from .api.homework import (
    DAILY_MAX_DEFAULT,
    DAILY_MAX_MAX,
    DAILY_MAX_STEP,
    DEFAULT_WEIGHT,
    KIND_HOMEWORK,
    LABEL_KINDS,
    LABEL_NAME_MAX,
    TYPE_KEYS,
    WEEKDAY_MAX_MIN,
    WEIGHT_MAX,
    WEIGHT_MIN,
    LabelOption,
    Weights,
    default_label_type_key,
    label_options_to_stored,
    merge_subject_weights,
    subjects_of,
    valid_weekday_max,
)
from .coach import (
    guidelines_of,
    parent_guidelines_of,
)
from .coach_text import DEFAULT_GUIDELINES, DEFAULT_PARENT_GUIDELINES
from .const import (
    CHILD_ID,
    CHILD_NAME,
    CHILD_SHORT_NAME,
    COACH_ENABLED,
    COACH_GUIDELINES,
    COACH_PARENTS,
    COACH_RESET,
    COACH_STUDENTS,
    COACH_USERS,
    CONF_CHILDREN,
    CONF_COACH,
    CONF_HOST,
    CONF_INTERVAL,
    CONF_LABELS,
    CONF_PARENT_GUIDELINES,
    CONF_STUDY_TIMER,
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
    CONF_WEIGHTS,
    DOMAIN,
    GUIDELINES_MAX,
    INTERVAL_MAX,
    INTERVAL_MIN,
    INTERVAL_MINUTES,
    WEEKS_AHEAD,
    WEEKS_AHEAD_MAX,
    WEEKS_BACK,
    WEEKS_BACK_MAX,
)
from .homework import new_label_id, options_with_weekdays, weekday_options
from .pending import peek_retained_login
from .proposals import WEEKDAY_NAMES
from .roles import coach_settings, parent_users, student_users
from .timer import notify_services

_LOGGER = logging.getLogger(__name__)

# The field of the study timer step: the notify services of a child.
CONF_TARGETS = "targets"

# The fields of the daily maximum step: one per weekday, Monday first.
WEEKDAY_FIELDS = tuple(f"daily_max_{name}" for name in WEEKDAY_NAMES)


def child_entry(person: Person) -> dict[str, Any]:
    """The stored form of a child in the config entry data."""
    return {
        CHILD_ID: person.id,
        CHILD_NAME: person.name,
        CHILD_SHORT_NAME: person.first_name or person.initials or person.name,
    }


def children_in_other_entries(
    hass: HomeAssistant,
    host: str,
    exclude_entry_id: str | None,
    also_exclude: str | None = None,
) -> set[int]:
    """Child ids of the same school that another entry already has a calendar for."""
    taken: set[int] = set()
    for other in hass.config_entries.async_entries(DOMAIN):
        if (
            other.entry_id in (exclude_entry_id, also_exclude)
            or other.data.get(CONF_HOST) != host
        ):
            continue
        taken.update(int(c[CHILD_ID]) for c in other.data.get(CONF_CHILDREN, []))
    return taken


def _number(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
        )
    )


def _weight_number() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=WEIGHT_MIN,
            max=WEIGHT_MAX,
            step=0.5,
            mode=NumberSelectorMode.BOX,
        )
    )


class MagisterOptionsFlow(OptionsFlow):
    """A menu: general settings, homework weights and the manual labels."""

    def __init__(self) -> None:
        """Initialise the flow."""
        self._children: dict[int, dict[str, Any]] | None = None
        self._weights_child: int | None = None
        self._type_weights: dict[str, float] = {}
        self._label_weights: dict[str, float] = {}
        self._labels_child: int | None = None
        self._label_id: str | None = None
        self._coach_child: int | None = None
        self._context_child: int | None = None
        self._context_subject: str | None = None
        self._daily_max_child: int | None = None
        self._timer_child: int | None = None

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
        """Choose between the general settings, the homework weights and the labels."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "weights",
                "daily_max",
                "labels",
                "coach",
                "study_timer",
            ],
        )

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and save the general options."""
        entry = self.config_entry
        if self._children is None and (
            reason := await self._async_fetch_children(entry)
        ):
            return self.async_abort(reason=reason)
        assert self._children is not None
        taken = children_in_other_entries(
            self.hass, str(entry.data[CONF_HOST]), entry.entry_id
        )
        current = [int(c[CHILD_ID]) for c in entry.data[CONF_CHILDREN]]
        # Children this entry already has stay offered, so the form can always be saved.
        offered = {
            k: v for k, v in self._children.items() if k not in taken or k in current
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = {int(value) for value in user_input[CONF_CHILDREN]}
            if selected & (taken - set(current)):
                errors["base"] = "child_already_configured"
            elif not selected:
                errors["base"] = "no_children_selected"
            else:
                options = {
                    **entry.options,
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
                            for child_id, child in offered.items()
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
                            for child_id, child in offered.items()
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
            step_id="general",
            data_schema=self.add_suggested_values_to_schema(schema, values),
            errors=errors,
        )

    # -- homework weights ---------------------------------------------------

    def _child_names(self) -> dict[int, str]:
        return {
            int(c[CHILD_ID]): str(c[CHILD_NAME])
            for c in self.config_entry.data[CONF_CHILDREN]
        }

    def _stored_weights(self) -> Weights:
        assert self._weights_child is not None
        stored = self.config_entry.options.get(CONF_WEIGHTS)
        child = (
            stored.get(str(self._weights_child)) if isinstance(stored, dict) else None
        )
        return Weights.from_options(child)

    async def async_step_weights(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the child whose homework weights are changed."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")
        names = self._child_names()
        if user_input is not None or len(names) == 1:
            self._weights_child = (
                int(user_input["child"]) if user_input else next(iter(names))
            )
            return await self.async_step_weights_types()
        return self.async_show_form(
            step_id="weights",
            data_schema=probatio.Schema(
                {
                    probatio.Required("child"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=str(child_id), label=name)
                                for child_id, name in names.items()
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_weights_types(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Weights per type (Huiswerk, Proefwerk, Tentamen, SO, MO)."""
        if user_input is not None:
            self._type_weights = {
                key: float(user_input[key]) for key in TYPE_KEYS if key in user_input
            }
            return await self.async_step_weights_labels()
        stored = self._stored_weights()
        schema = probatio.Schema(
            {probatio.Required(key): _weight_number() for key in TYPE_KEYS}
        )
        return self.async_show_form(
            step_id="weights_types",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                {key: stored.types.get(key, DEFAULT_WEIGHT) for key in TYPE_KEYS},
            ),
            description_placeholders={
                "child": self._child_names()[self._weights_child or 0]
            },
        )

    async def async_step_weights_labels(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Weights per manual label of the child (by label name)."""
        assert self._weights_child is not None
        options = [
            o
            for o in self._label_options(self._weights_child)
            if default_label_type_key(o.id) is None
        ]
        if user_input is not None:
            by_name = {o.name: o.id for o in options}
            self._label_weights = {
                by_name[name]: float(value)
                for name, value in user_input.items()
                if name in by_name
            }
            return await self.async_step_weights_subjects()
        if not options:
            self._label_weights = {}
            return await self.async_step_weights_subjects()
        stored = self._stored_weights()
        schema = probatio.Schema(
            {probatio.Required(o.name): _weight_number() for o in options}
        )
        return self.async_show_form(
            step_id="weights_labels",
            data_schema=self.add_suggested_values_to_schema(
                schema, {o.name: stored.label_weight(o.id) for o in options}
            ),
            description_placeholders={
                "child": self._child_names()[self._weights_child]
            },
        )

    async def async_step_weights_subjects(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Weights per subject in the child's current homework data."""
        assert self._weights_child is not None
        subjects = subjects_of(
            self.config_entry.runtime_data.homework.items(self._weights_child)
        )
        if user_input is None and subjects:
            stored = self._stored_weights()
            schema = probatio.Schema(
                {probatio.Required(name): _weight_number() for name in subjects}
            )
            return self.async_show_form(
                step_id="weights_subjects",
                data_schema=self.add_suggested_values_to_schema(
                    schema, {name: stored.subject_weight(name) for name in subjects}
                ),
            )
        present = {name: float(value) for name, value in (user_input or {}).items()}
        return self._save_weights(present)

    def _save_weights(self, present_subjects: dict[str, float]) -> ConfigFlowResult:
        """Store only the values other than 1; keep subjects not present now."""
        entry = self.config_entry
        stored = self._stored_weights()
        types = {k: w for k, w in self._type_weights.items() if w != DEFAULT_WEIGHT}
        labels = {k: w for k, w in self._label_weights.items() if w != DEFAULT_WEIGHT}
        subjects = merge_subject_weights(stored.subjects, present_subjects)
        weights = {
            key: dict(value)
            for key, value in (entry.options.get(CONF_WEIGHTS) or {}).items()
        }
        child_key = str(self._weights_child)
        weekday_values = weekday_options(stored.daily_max_weekdays)
        if types or subjects or labels or weekday_values:
            weights[child_key] = {"types": types, "subjects": subjects}
            if labels:
                weights[child_key]["labels"] = labels
            weights[child_key].update(weekday_values)
        else:
            weights.pop(child_key, None)
        options = dict(entry.options)
        if weights:
            options[CONF_WEIGHTS] = weights
        else:
            options.pop(CONF_WEIGHTS, None)
        return self.async_create_entry(data=options)

    # -- daily maximum --------------------------------------------------------

    async def async_step_daily_max(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the child whose daily study maximum is changed."""
        names = self._child_names()
        if user_input is not None or len(names) == 1:
            self._daily_max_child = (
                int(user_input["child"]) if user_input else next(iter(names))
            )
            return await self.async_step_daily_max_settings()
        return self.async_show_form(
            step_id="daily_max",
            data_schema=probatio.Schema(
                {
                    probatio.Required("child"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=str(child_id), label=name)
                                for child_id, name in names.items()
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_daily_max_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The study minutes per weekday (Monday to Sunday) for the AI and the card."""
        assert self._daily_max_child is not None
        entry = self.config_entry
        child_key = str(self._daily_max_child)
        stored = entry.options.get(CONF_WEIGHTS)
        current = Weights.from_options(
            stored.get(child_key) if isinstance(stored, dict) else None
        ).daily_max_weekdays
        errors: dict[str, str] = {}
        if user_input is not None:
            values = [valid_weekday_max(user_input[key]) for key in WEEKDAY_FIELDS]
            for key, value in zip(WEEKDAY_FIELDS, values, strict=True):
                if value is None:
                    errors[key] = "invalid_daily_max"
            if not errors:
                return self._save_daily_max(tuple(v for v in values if v is not None))
        schema = probatio.Schema(
            {
                probatio.Required(key): NumberSelector(
                    NumberSelectorConfig(
                        min=WEEKDAY_MAX_MIN,
                        max=DAILY_MAX_MAX,
                        step=DAILY_MAX_STEP,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                )
                for key in WEEKDAY_FIELDS
            }
        )
        return self.async_show_form(
            step_id="daily_max_settings",
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or dict(zip(WEEKDAY_FIELDS, current, strict=True))
            ),
            errors=errors,
            description_placeholders={
                "child": self._child_names()[self._daily_max_child],
                "default": str(DAILY_MAX_DEFAULT),
            },
        )

    def _save_daily_max(self, weekdays: tuple[int, ...]) -> ConfigFlowResult:
        """Store the maximums with the child's weights (no reload); default: removed."""
        assert self._daily_max_child is not None
        return self.async_create_entry(
            data=options_with_weekdays(
                self.config_entry.options, self._daily_max_child, weekdays
            )
        )

    # -- manual labels ------------------------------------------------------

    def _label_options(self, child_id: int) -> list[LabelOption]:
        options: list[LabelOption] = (
            self.config_entry.runtime_data.homework.label_options(child_id)
        )
        return options

    def _label_name_schema(self, kind: str = KIND_HOMEWORK) -> dict[Any, Any]:
        return {
            probatio.Required("name"): TextSelector(),
            probatio.Required("kind", default=kind): SelectSelector(
                SelectSelectorConfig(
                    options=list(LABEL_KINDS),
                    translation_key="label_kind",
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }

    def _save_labels(self, labels: list[LabelOption]) -> ConfigFlowResult:
        """Store the labels of the child being edited (no reload, see the snapshot)."""
        entry = self.config_entry
        stored = {
            key: list(value)
            for key, value in (entry.options.get(CONF_LABELS) or {}).items()
        }
        stored[str(self._labels_child)] = label_options_to_stored(labels)
        return self.async_create_entry(data={**entry.options, CONF_LABELS: stored})

    def _name_error(self, name: str, exclude_id: str | None = None) -> str | None:
        """An error key when a label name is empty, too long or already used."""
        assert self._labels_child is not None
        if not name:
            return "name_required"
        if "[" in name or "]" in name:
            return "name_invalid_chars"
        if len(name) > LABEL_NAME_MAX:
            return "name_too_long"
        wanted = name.casefold()
        if any(
            o.name.casefold() == wanted and o.id != exclude_id
            for o in self._label_options(self._labels_child)
        ):
            return "name_exists"
        return None

    def _label_select(self, step_id: str, errors: dict[str, str]) -> ConfigFlowResult:
        assert self._labels_child is not None
        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(
                {
                    probatio.Required("label"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=o.id, label=o.name)
                                for o in self._label_options(self._labels_child)
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            errors=errors,
            description_placeholders={"child": self._child_names()[self._labels_child]},
        )

    async def async_step_labels(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the child whose labels are changed."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")
        names = self._child_names()
        if user_input is not None or len(names) == 1:
            self._labels_child = (
                int(user_input["child"]) if user_input else next(iter(names))
            )
            return await self.async_step_labels_menu()
        return self.async_show_form(
            step_id="labels",
            data_schema=probatio.Schema(
                {
                    probatio.Required("child"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=str(child_id), label=name)
                                for child_id, name in names.items()
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_labels_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add, change or delete a label of the chosen child."""
        assert self._labels_child is not None
        menu = ["label_add"]
        if self._label_options(self._labels_child):
            menu += ["label_edit", "label_delete"]
        return self.async_show_menu(
            step_id="labels_menu",
            menu_options=menu,
            description_placeholders={"child": self._child_names()[self._labels_child]},
        )

    async def async_step_label_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a label with a name and a kind."""
        assert self._labels_child is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input["name"]).strip()
            if error := self._name_error(name):
                errors["name"] = error
            else:
                labels = self._label_options(self._labels_child)
                labels.append(LabelOption(new_label_id(), name, user_input["kind"]))
                return self._save_labels(labels)
        return self.async_show_form(
            step_id="label_add",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(self._label_name_schema()), user_input
            ),
            errors=errors,
        )

    async def async_step_label_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the label to rename or to give another kind."""
        if user_input is not None:
            self._label_id = user_input["label"]
            return await self.async_step_label_edit_details()
        return self._label_select("label_edit", {})

    async def async_step_label_edit_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the name and the kind of the chosen label."""
        assert self._labels_child is not None
        labels = self._label_options(self._labels_child)
        current = next((o for o in labels if o.id == self._label_id), None)
        if current is None:
            return self.async_abort(reason="label_gone")
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input["name"]).strip()
            if error := self._name_error(name, current.id):
                errors["name"] = error
            else:
                return self._save_labels(
                    [
                        LabelOption(o.id, name, user_input["kind"])
                        if o.id == current.id
                        else o
                        for o in labels
                    ]
                )
        return self.async_show_form(
            step_id="label_edit_details",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(self._label_name_schema(current.kind)),
                user_input or {"name": current.name, "kind": current.kind},
            ),
            errors=errors,
            description_placeholders={"label": current.name},
        )

    async def async_step_label_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Delete a label that is not in use."""
        assert self._labels_child is not None
        if user_input is None:
            return self._label_select("label_delete", {})
        label_id: str = user_input["label"]
        if self.config_entry.runtime_data.homework.label_in_use(
            self._labels_child, label_id
        ):
            return self._label_select("label_delete", {"base": "label_in_use"})
        self.config_entry.runtime_data.homework.drop_label_references(
            self._labels_child, label_id
        )
        return self._save_labels(
            [o for o in self._label_options(self._labels_child) if o.id != label_id]
        )

    # -- study timer ----------------------------------------------------------

    async def async_step_study_timer(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the child whose study timer notifications are set up."""
        names = self._child_names()
        if user_input is not None or len(names) == 1:
            self._timer_child = (
                int(user_input["child"]) if user_input else next(iter(names))
            )
            return await self.async_step_study_timer_targets()
        return self.async_show_form(
            step_id="study_timer",
            data_schema=probatio.Schema(
                {
                    probatio.Required("child"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=str(child_id), label=name)
                                for child_id, name in names.items()
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_study_timer_targets(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the companion-app notify services of the child (no reload)."""
        assert self._timer_child is not None
        entry = self.config_entry
        raw = entry.options.get(CONF_STUDY_TIMER)
        stored: dict[str, Any] = raw if isinstance(raw, dict) else {}
        chosen = stored.get(str(self._timer_child))
        current = (
            [t for t in chosen if isinstance(t, str)]
            if isinstance(chosen, list)
            else []
        )
        # A chosen service that is gone stays in the list, so it can be removed.
        available = sorted({*notify_services(self.hass), *current})
        if user_input is not None:
            targets = sorted(
                {t for t in user_input.get(CONF_TARGETS) or [] if t in available}
            )
            timers: dict[str, Any] = {
                key: list(value)
                for key, value in stored.items()
                if isinstance(value, list)
            }
            if targets:
                timers[str(self._timer_child)] = targets
            else:
                timers.pop(str(self._timer_child), None)
            options = dict(entry.options)
            if timers:
                options[CONF_STUDY_TIMER] = timers
            else:
                options.pop(CONF_STUDY_TIMER, None)
            return self.async_create_entry(data=options)
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_TARGETS): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=name, label=f"notify.{name}")
                            for name in available
                        ],
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="study_timer_targets",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_TARGETS: current}
            ),
            description_placeholders={"child": self._child_names()[self._timer_child]},
        )

    # -- AI coach -----------------------------------------------------------

    async def async_step_coach(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The AI coach: settings per child, or the parent guidelines."""
        return self.async_show_menu(
            step_id="coach",
            menu_options=["coach_child", "coach_parent", "coach_context"],
        )

    async def async_step_coach_context(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Clear the context notes of the AI coach: choose the child."""
        names = self._child_names()
        if user_input is not None or len(names) == 1:
            self._context_child = (
                int(user_input["child"]) if user_input else next(iter(names))
            )
            return await self.async_step_coach_context_scope()
        return self.async_show_form(
            step_id="coach_context",
            data_schema=probatio.Schema(
                {
                    probatio.Required("child"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=str(child_id), label=name)
                                for child_id, name in names.items()
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_coach_context_scope(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """All context of the child, or one subject (only subjects with notes)."""
        assert self._context_child is not None
        book = self.config_entry.runtime_data.homework.context
        if book.count(self._context_child) == 0:
            return self.async_abort(reason="no_context")
        subjects = book.subjects_with_notes(self._context_child)
        if user_input is not None:
            chosen = user_input.get("subject") or None
            # Only a subject that has notes (or none: all context); else ask again.
            if chosen is None or chosen in subjects:
                self._context_subject = chosen
                return await self.async_step_coach_context_confirm()
        return self.async_show_form(
            step_id="coach_context_scope",
            data_schema=probatio.Schema(
                {
                    probatio.Optional("subject"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=name, label=name)
                                for name in subjects
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={
                "child": self._child_names()[self._context_child],
            },
        )

    async def async_step_coach_context_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show how many notes will be deleted; submitting deletes them."""
        assert self._context_child is not None
        book = self.config_entry.runtime_data.homework.context
        if user_input is not None:
            deleted = book.clear(self._context_child, self._context_subject)
            return self.async_abort(
                reason="context_cleared",
                description_placeholders={"count": str(deleted)},
            )
        return self.async_show_form(
            step_id="coach_context_confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={
                "child": self._child_names()[self._context_child],
                "count": str(book.count(self._context_child, self._context_subject)),
                "subject": self._context_subject or "\u2013",
            },
        )

    async def async_step_coach_child(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the child whose AI coach is set up."""
        names = self._child_names()
        if user_input is not None or len(names) == 1:
            self._coach_child = (
                int(user_input["child"]) if user_input else next(iter(names))
            )
            return await self.async_step_coach_settings()
        return self.async_show_form(
            step_id="coach_child",
            data_schema=probatio.Schema(
                {
                    probatio.Required("child"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=str(child_id), label=name)
                                for child_id, name in names.items()
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_coach_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable the coach, link HA users per role and edit the student guidelines."""
        assert self._coach_child is not None
        entry = self.config_entry
        users = {
            user.id: user.name or user.id
            for user in await self.hass.auth.async_get_users()
            if user.is_active and not user.system_generated
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input.get(COACH_STUDENTS) or []) & set(
                user_input.get(COACH_PARENTS) or []
            ):
                errors[COACH_PARENTS] = "user_in_both_roles"
            elif (
                len(str(user_input.get(COACH_GUIDELINES) or "").strip())
                > GUIDELINES_MAX
            ):
                errors[COACH_GUIDELINES] = "guidelines_too_long"
            else:
                return self._save_coach(user_input, set(users))
        settings = coach_settings(entry, self._coach_child)
        suggested = user_input or {
            COACH_ENABLED: settings.get(COACH_ENABLED) is True,
            COACH_STUDENTS: [u for u in student_users(settings) if u in users],
            COACH_PARENTS: [u for u in parent_users(settings) if u in users],
            COACH_GUIDELINES: guidelines_of(settings),
            COACH_RESET: False,
        }
        user_select = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=user_id, label=name)
                    for user_id, name in users.items()
                ],
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        schema = probatio.Schema(
            {
                probatio.Required(COACH_ENABLED): BooleanSelector(),
                probatio.Optional(COACH_STUDENTS): user_select,
                probatio.Optional(COACH_PARENTS): user_select,
                probatio.Optional(COACH_GUIDELINES): TextSelector(
                    TextSelectorConfig(multiline=True)
                ),
                probatio.Optional(COACH_RESET): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="coach_settings",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders={
                "child": self._child_names()[self._coach_child],
                "max": str(GUIDELINES_MAX),
            },
        )

    def _save_coach(
        self, user_input: dict[str, Any], valid_users: set[str]
    ) -> ConfigFlowResult:
        """Store the coach settings of the child (applied without a reload)."""
        entry = self.config_entry
        text = str(user_input.get(COACH_GUIDELINES) or "").strip()
        if user_input.get(COACH_RESET) or text == DEFAULT_GUIDELINES.strip():
            text = ""
        stored: dict[str, Any] = {
            key: dict(value)
            for key, value in (entry.options.get(CONF_COACH) or {}).items()
        }
        setting: dict[str, Any] = {
            COACH_ENABLED: bool(user_input[COACH_ENABLED]),
            COACH_STUDENTS: sorted(
                {u for u in user_input.get(COACH_STUDENTS) or [] if u in valid_users}
            ),
            COACH_PARENTS: sorted(
                {u for u in user_input.get(COACH_PARENTS) or [] if u in valid_users}
            ),
        }
        # 1.6.0 mirror: the students (a parent-only child has none), so a downgrade
        # keeps the student links.
        setting[COACH_USERS] = [
            u for u in setting[COACH_STUDENTS] if u not in setting[COACH_PARENTS]
        ]
        if text:
            setting[COACH_GUIDELINES] = text
        if (
            setting[COACH_ENABLED]
            or setting[COACH_STUDENTS]
            or setting[COACH_PARENTS]
            or text
        ):
            stored[str(self._coach_child)] = setting
        else:
            stored.pop(str(self._coach_child), None)
        options = dict(entry.options)
        if stored:
            options[CONF_COACH] = stored
        else:
            options.pop(CONF_COACH, None)
        return self.async_create_entry(data=options)

    async def async_step_coach_parent(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the parent guidelines (Ouder-richtlijnen): one text per entry."""
        entry = self.config_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            text = str(user_input.get(CONF_PARENT_GUIDELINES) or "").strip()
            if len(text) > GUIDELINES_MAX:
                errors[CONF_PARENT_GUIDELINES] = "guidelines_too_long"
            else:
                if user_input.get(COACH_RESET) or text == DEFAULT_PARENT_GUIDELINES:
                    text = ""
                options = dict(entry.options)
                if text:
                    options[CONF_PARENT_GUIDELINES] = text
                else:
                    options.pop(CONF_PARENT_GUIDELINES, None)
                return self.async_create_entry(data=options)
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_PARENT_GUIDELINES): TextSelector(
                    TextSelectorConfig(multiline=True)
                ),
                probatio.Optional(COACH_RESET): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="coach_parent",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                user_input
                or {
                    CONF_PARENT_GUIDELINES: parent_guidelines_of(entry),
                    COACH_RESET: False,
                },
            ),
            errors=errors,
            description_placeholders={"max": str(GUIDELINES_MAX)},
        )
